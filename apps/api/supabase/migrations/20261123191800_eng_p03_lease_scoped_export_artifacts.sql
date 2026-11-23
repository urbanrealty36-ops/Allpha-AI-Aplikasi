-- ENG-P03 forward-only compatibility repair for lease-scoped export artifacts.
-- Preserve legacy completed exports while requiring new workers to bind artifacts
-- to the exact lease token used by the completion RPC.
create or replace function public.complete_account_export_job(
  p_job_id uuid,p_lease_token uuid,p_storage_path text,p_file_sha256 text,
  p_file_size_bytes bigint,p_manifest jsonb
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_user_id uuid;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_storage_path is null
     or p_file_sha256 is null
     or p_file_sha256 !~ '^[a-f0-9]{64}$'
     or p_file_size_bytes is null or p_file_size_bytes <= 0
     or p_manifest is null or jsonb_typeof(p_manifest) <> 'object' then
    raise exception 'invalid_export_receipt' using errcode = '22023';
  end if;
  update public.account_export_jobs j
  set status = 'succeeded',
      storage_bucket = 'account-exports',
      storage_path = p_storage_path,
      file_sha256 = p_file_sha256,
      file_size_bytes = p_file_size_bytes,
      manifest = p_manifest,
      completed_at = pg_catalog.now(),
      lease_token = null,
      lease_owner = null,
      lease_expires_at = null,
      error_code = null,
      updated_at = pg_catalog.now()
  where j.id = p_job_id
    and j.status = 'running'
    and j.lease_token = p_lease_token
    and j.lease_expires_at > pg_catalog.now()
    and p_storage_path in (
      j.user_id::text || '/' || j.id::text || '.json.gz',
      j.user_id::text || '/' || j.id::text || '/' || p_lease_token::text || '.json.gz'
    );
  if not found then return false; end if;
  select j.user_id into v_user_id from public.account_export_jobs j where j.id = p_job_id;
  insert into public.account_lifecycle_events(export_job_id,user_id,subject_ref,event_type,metadata)
  values (p_job_id,v_user_id,encode(extensions.digest(v_user_id::text,'sha256'),'hex'),'export_completed',
          jsonb_build_object('file_size_bytes',p_file_size_bytes,'file_sha256',p_file_sha256));
  return true;
end;
$$;

revoke all on function public.complete_account_export_job(uuid,uuid,text,text,bigint,jsonb)
  from public, anon, authenticated;
grant execute on function public.complete_account_export_job(uuid,uuid,text,text,bigint,jsonb)
  to service_role;


-- Forward repair for the append-only consent RPC. The historical 91700
-- migration remains immutable; its OUT parameter user_id shadowed the
-- unqualified ON CONFLICT target at runtime.
create or replace function public.record_account_consent_event_for_actor(
  p_actor_user_id uuid,
  p_consent_type text,
  p_policy_version text,
  p_decision text,
  p_source text,
  p_idempotency_key text
)
returns table(
  id uuid,
  user_id uuid,
  consent_type text,
  policy_version text,
  decision text,
  source text,
  idempotency_key text,
  recorded_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $consent_event$
declare
  v_event public.user_consent_events%rowtype;
  v_previous_decision text;
  v_previous_policy_version text;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_actor_user_id is null or not exists(select 1 from auth.users u where u.id=p_actor_user_id) then
    raise exception 'consent_actor_not_found' using errcode = 'P0002';
  end if;
  if p_consent_type is null or p_consent_type not in ('terms_of_service','privacy_policy','product_updates')
     or p_policy_version is null or char_length(p_policy_version) not between 1 and 40
     or p_decision is null or p_decision not in ('granted','declined','revoked')
     or p_source is null or p_source not in ('onboarding','account_settings','policy_refresh')
     or p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 128 then
    raise exception 'consent_event_input_invalid' using errcode = '22023';
  end if;
  if p_decision='revoked' and p_consent_type<>'product_updates' then
    raise exception 'required_policy_withdrawal_not_supported' using errcode = '42501';
  end if;

  select e.decision,e.policy_version into v_previous_decision,v_previous_policy_version
    from public.user_consent_events e
   where e.user_id=p_actor_user_id and e.consent_type=p_consent_type
   order by e.recorded_at desc,e.id desc
   limit 1;
  if p_consent_type<>'product_updates'
     and v_previous_decision='granted'
     and v_previous_policy_version=p_policy_version
     and p_decision='declined' then
    raise exception 'required_policy_withdrawal_requires_account_lifecycle' using errcode = '42501';
  end if;

  insert into public.user_consent_events(
    user_id,consent_type,policy_version,decision,source,idempotency_key
  ) values (
    p_actor_user_id,p_consent_type,p_policy_version,p_decision,p_source,p_idempotency_key
  )
  on conflict on constraint user_consent_events_user_id_idempotency_key_key do nothing
  returning * into v_event;

  if not found then
    select * into v_event
      from public.user_consent_events e
     where e.user_id=p_actor_user_id and e.idempotency_key=p_idempotency_key;
    if v_event.consent_type is distinct from p_consent_type
       or v_event.policy_version is distinct from p_policy_version
       or v_event.decision is distinct from p_decision
       or v_event.source is distinct from p_source then
      raise exception 'consent_idempotency_key_conflict' using errcode = '23505';
    end if;
  end if;

  return query select v_event.id,v_event.user_id,v_event.consent_type,
    v_event.policy_version,v_event.decision,v_event.source,
    v_event.idempotency_key,v_event.recorded_at;
end;
$consent_event$;

revoke all on function public.record_account_consent_event_for_actor(uuid,text,text,text,text,text)
  from public,anon,authenticated;
grant execute on function public.record_account_consent_event_for_actor(uuid,text,text,text,text,text)
  to service_role;
