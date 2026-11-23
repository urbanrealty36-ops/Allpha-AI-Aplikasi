-- ENG-P03 forward migration: append-only consent decision history.
-- The existing user_consents table remains readable as legacy history; new
-- consent writes go through a service-role-only FastAPI RPC so clients cannot
-- forge policy versions or bypass the approved-version check in the API.

create table if not exists public.user_consent_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  consent_type text not null check (consent_type in ('terms_of_service','privacy_policy','product_updates')),
  policy_version text not null check (char_length(policy_version) between 1 and 40),
  decision text not null check (decision in ('granted','declined','revoked')),
  source text not null check (source in ('onboarding','account_settings','policy_refresh')),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 128),
  recorded_at timestamptz not null default now(),
  unique (user_id,idempotency_key)
);

create index if not exists user_consent_events_user_history_idx
  on public.user_consent_events(user_id,consent_type,recorded_at desc,id desc);

-- Preserve the pre-existing append-only decisions when moving reads to the
-- richer event model. No consent is fabricated; only existing rows are copied.
insert into public.user_consent_events(
  user_id,consent_type,policy_version,decision,source,idempotency_key,recorded_at
)
select c.user_id,c.consent_type,c.policy_version,
       case when c.granted then 'granted' else 'declined' end,
       'policy_refresh',
       'legacy:' || md5(concat_ws(':',c.user_id::text,c.consent_type,c.policy_version,c.recorded_at::text)),
       c.recorded_at
  from public.user_consents c
on conflict (user_id,idempotency_key) do nothing;

-- Include consent events in the existing canonical account-export allowlist.
insert into private.account_export_sources(source_key,table_name,filter_kind,owner_columns,sort_order)
values ('consent_events','user_consent_events','owner_columns',array['user_id'],31)
on conflict (source_key) do nothing;

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

  select e.decision into v_previous_decision
    from public.user_consent_events e
   where e.user_id=p_actor_user_id and e.consent_type=p_consent_type
   order by e.recorded_at desc,e.id desc
   limit 1;
  if p_consent_type<>'product_updates'
     and v_previous_decision='granted'
     and p_decision='declined' then
    raise exception 'required_policy_withdrawal_requires_account_lifecycle' using errcode = '42501';
  end if;

  insert into public.user_consent_events(
    user_id,consent_type,policy_version,decision,source,idempotency_key
  ) values (
    p_actor_user_id,p_consent_type,p_policy_version,p_decision,p_source,p_idempotency_key
  )
  on conflict (user_id,idempotency_key) do nothing
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

alter table public.user_consent_events enable row level security;
drop policy if exists user_consent_events_select_self on public.user_consent_events;
create policy user_consent_events_select_self on public.user_consent_events
for select to authenticated using (user_id=(select auth.uid()));

-- Retire the legacy direct-write path. The API validates the active policy
-- version and invokes the service-only RPC; clients can read their own history.
drop policy if exists user_consents_insert_self on public.user_consents;
revoke all privileges on public.user_consents from anon,authenticated;
grant select on public.user_consents to authenticated;
revoke all privileges on public.user_consent_events from anon,authenticated;
grant select on public.user_consent_events to authenticated;
grant select,insert,update,delete on public.user_consent_events to service_role;

revoke all on function public.record_account_consent_event_for_actor(uuid,text,text,text,text,text)
  from public,anon,authenticated;
grant execute on function public.record_account_consent_event_for_actor(uuid,text,text,text,text,text)
  to service_role;
