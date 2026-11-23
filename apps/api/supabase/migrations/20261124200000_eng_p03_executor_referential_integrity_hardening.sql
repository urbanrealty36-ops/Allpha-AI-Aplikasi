-- ENG-P03: close remaining executor referential-integrity gaps.
-- This is additive/forward-only and does not execute any account deletion.

alter table public.account_deletion_storage_jobs
  drop constraint if exists account_deletion_storage_jobs_source_key_check;
alter table public.account_deletion_storage_jobs
  add constraint account_deletion_storage_jobs_source_key_check
  check (source_key = any (array[
    'agent_knowledge_sources','content_media','generation_artifacts',
    'account_export_jobs','generation_artifact_deletions'
  ]::text[]));

-- Ownership-transfer history must survive deletion of either the former owner or successor.
alter table public.account_deletion_ownership_transfers
  drop constraint account_deletion_ownership_transfers_user_id_fkey;
alter table public.account_deletion_ownership_transfers
  add constraint account_deletion_ownership_transfers_user_id_fkey
  foreign key (user_id) references private.account_identity_subjects(subject_id)
  on delete restrict not valid;
alter table public.account_deletion_ownership_transfers
  validate constraint account_deletion_ownership_transfers_user_id_fkey;

alter table public.account_deletion_ownership_transfers
  drop constraint account_deletion_ownership_transfers_successor_user_id_fkey;
alter table public.account_deletion_ownership_transfers
  add constraint account_deletion_ownership_transfers_successor_user_id_fkey
  foreign key (successor_user_id) references private.account_identity_subjects(subject_id)
  on delete restrict not valid;
alter table public.account_deletion_ownership_transfers
  validate constraint account_deletion_ownership_transfers_successor_user_id_fkey;

create or replace function public.set_my_account_deletion_ownership_transfer(
  p_request_id uuid,
  p_resource_type text,
  p_resource_id uuid,
  p_successor_user_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_actor uuid := auth.uid();
  v_request public.account_deletion_requests%rowtype;
begin
  if v_actor is null or coalesce(auth.role(),'') <> 'authenticated' then
    raise exception 'authenticated_account_owner_required' using errcode='42501';
  end if;
  if p_request_id is null or p_resource_id is null or p_successor_user_id is null
     or p_resource_type not in ('agent','organization') then
    raise exception 'account_deletion_transfer_arguments_invalid' using errcode='22023';
  end if;
  if p_successor_user_id = v_actor then
    raise exception 'account_deletion_transfer_successor_must_differ' using errcode='22023';
  end if;

  select * into v_request
    from public.account_deletion_requests r
   where r.id=p_request_id and r.user_id=v_actor
   for update;
  if not found or v_request.status not in ('awaiting_policy','scheduled','blocked_dependency') then
    raise exception 'account_deletion_transfer_request_unavailable' using errcode='42501';
  end if;
  if not exists (
    select 1 from public.profiles p
     where p.id=p_successor_user_id and p.account_status='active'
  ) then
    raise exception 'account_deletion_transfer_successor_not_active' using errcode='23514';
  end if;

  if p_resource_type='agent' then
    if not exists (
      select 1 from public.agent_ownerships ao
      join public.ai_agents a on a.id=ao.agent_id
      where ao.agent_id=p_resource_id and ao.owner_user_id=v_actor
        and ao.ownership_role='owner' and ao.status='active'
    ) then
      raise exception 'account_deletion_agent_ownership_not_found' using errcode='42501';
    end if;
  elsif p_resource_type='organization' then
    if not exists (
      select 1 from public.organizations o
      join public.organization_memberships m
        on m.organization_id=o.id and m.user_id=p_successor_user_id
      where o.id=p_resource_id and o.owner_id=v_actor
    ) then
      raise exception 'account_deletion_organization_successor_must_be_member' using errcode='42501';
    end if;
  end if;

  insert into private.account_identity_subjects(subject_id,subject_ref,status)
  select u.id,encode(digest(u.id::text,'sha256'),'hex'),'active'
    from auth.users u where u.id in (v_actor,p_successor_user_id)
  on conflict(subject_id) do nothing;
  if (select count(*) from private.account_identity_subjects s
       where s.subject_id in (v_actor,p_successor_user_id) and s.status='active') <> 2 then
    raise exception 'account_deletion_transfer_identity_subject_unavailable' using errcode='23514';
  end if;

  insert into public.account_deletion_ownership_transfers(
    request_id,user_id,resource_type,resource_id,successor_user_id,status
  ) values (
    p_request_id,v_actor,p_resource_type,p_resource_id,p_successor_user_id,'requested'
  )
  on conflict (request_id,resource_type,resource_id)
  do update set successor_user_id=excluded.successor_user_id,status='requested',applied_at=null;

  return jsonb_build_object(
    'request_id',p_request_id,
    'resource_type',p_resource_type,
    'resource_id',p_resource_id,
    'successor_user_id',p_successor_user_id,
    'status','requested'
  );
end;
$$;
revoke all on function public.set_my_account_deletion_ownership_transfer(uuid,text,uuid,uuid)
  from public,anon,service_role;
grant execute on function public.set_my_account_deletion_ownership_transfer(uuid,text,uuid,uuid)
  to authenticated;

-- Execution job retains the irreversible audit result through subject_ref, not a raw Auth UUID.
alter table public.account_deletion_execution_jobs
  alter column user_id drop not null;

do $$
declare
  v_definition text;
  v_old text := $old$
  update public.account_deletion_execution_jobs set status='completed',completed_at=clock_timestamp(),
    lease_token=null,lease_owner=null,lease_expires_at=null,error_code=null,updated_at=clock_timestamp()
  where id=v_job.id;
$old$;
  v_new text := $new$
  update public.account_deletion_execution_jobs set status='completed',user_id=null,
    completed_at=clock_timestamp(),lease_token=null,lease_owner=null,lease_expires_at=null,
    error_code=null,updated_at=clock_timestamp()
  where id=v_job.id;
$new$;
begin
  v_definition:=pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure);
  if position(v_new in v_definition)>0 then return; end if;
  if position(v_old in v_definition)=0 then
    raise exception 'account_deletion_execution_job_subject_redaction_anchor_missing';
  end if;
  execute replace(v_definition,v_old,v_new);
end;
$$;
