-- SOURCE ONLY — WP-07 external Consumer grant revocation and generation lifecycle.
-- Revoke permission atomically with queued-job cancellation and running-job reconciliation.
-- Do not apply to canonical production or staging during the current source-only work window.
begin;

create table if not exists public.agent_consumer_grant_events (
  id uuid primary key default gen_random_uuid(),
  grant_id uuid not null references public.agent_consumer_grants(id) on delete restrict,
  requester_user_id uuid not null references auth.users(id) on delete restrict,
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  agent_id uuid not null references public.ai_agents(id) on delete restrict,
  actor_user_id uuid not null references auth.users(id) on delete restrict,
  event_type text not null check (event_type in ('created','revoked')),
  reason_code text not null check (char_length(reason_code) between 1 and 120),
  details jsonb not null default '{}'::jsonb check (jsonb_typeof(details)='object'),
  created_at timestamptz not null default now()
);
create or replace function public.audit_agent_consumer_grant_created()
returns trigger language plpgsql security definer set search_path = ''
as $
begin
  insert into public.agent_consumer_grant_events(
    grant_id,requester_user_id,owner_user_id,agent_id,actor_user_id,
    event_type,reason_code,details
  ) values (
    new.id,new.requester_user_id,new.owner_user_id,new.agent_id,new.granted_by,
    'created','grant_created',
    jsonb_build_object(
      'agent_version',new.agent_version,'skill_id',new.skill_id,
      'skill_version',new.skill_version,'runtime_policy_version',new.runtime_policy_version,
      'granted_scopes',new.granted_scopes,'capability_id',new.capability_id,
      'credit_scheme_version',new.credit_scheme_version,'tariff_version',new.tariff_version,
      'entitlement_version',new.entitlement_version,'payer_role',new.payer_role,
      'expires_at',new.expires_at
    )
  );
  return new;
end;
$;

drop trigger if exists agent_consumer_grant_created_audit on public.agent_consumer_grants;
create trigger agent_consumer_grant_created_audit
after insert on public.agent_consumer_grants
for each row execute function public.audit_agent_consumer_grant_created();

revoke all on function public.audit_agent_consumer_grant_created()
  from public,anon,authenticated;
grant execute on function public.audit_agent_consumer_grant_created()
  to service_role;

create index if not exists agent_consumer_grant_events_owner_created_idx
  on public.agent_consumer_grant_events(owner_user_id, created_at desc);
create index if not exists agent_consumer_grant_events_grant_created_idx
  on public.agent_consumer_grant_events(grant_id, created_at desc);

alter table public.agent_consumer_grant_events enable row level security;
revoke all on public.agent_consumer_grant_events from public,anon,authenticated,service_role;
grant select,insert on public.agent_consumer_grant_events to service_role;

create or replace function public.agent_consumer_grant_revoke(
  p_grant_id uuid,p_owner_user_id uuid,p_reason text default 'owner_revoked'
) returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
  v_grant public.agent_consumer_grants;
  v_job record;
  v_reason text := left(coalesce(nullif(btrim(p_reason),''),'owner_revoked'),120);
  v_queued_cancelled integer := 0;
  v_running_reconciled integer := 0;
  v_already_revoked boolean := false;
begin
  if p_grant_id is null or p_owner_user_id is null then
    raise exception 'CONSUMER_GRANT_REVOKE_COMMAND_INVALID' using errcode='22023';
  end if;

  select * into v_grant from public.agent_consumer_grants
    where id=p_grant_id and owner_user_id=p_owner_user_id
    for update;
  if not found then
    raise exception 'CONSUMER_GRANT_NOT_FOUND' using errcode='P0002';
  end if;

  v_already_revoked := v_grant.status='revoked';
  if not v_already_revoked then
    update public.agent_consumer_grants set
      status='revoked',revoked_by=p_owner_user_id,revoked_at=now(),
      revoke_reason=v_reason,updated_at=now()
    where id=v_grant.id returning * into v_grant;
  end if;

  -- A queued job has not called the provider. Release only when the approved
  -- failure policy allows it; otherwise retain the reservation for reconciliation.
  for v_job in
    select id,reservation_id,policy_version,allow_definitive_failure_release
    from public.generation_jobs
    where consumer_grant_id=v_grant.id and status='queued'
    for update
  loop
    if v_job.allow_definitive_failure_release then
      begin
        perform public.credit_ledger_release(jsonb_build_object(
          'reservation_id',v_job.reservation_id,
          'idempotency_key','generation-revoke-release:'||v_job.id::text,
          'policy_version',v_job.policy_version,
          'reason_code','consumer_grant_revoked_before_execution'
        ));
        update public.generation_jobs set status='cancelled',
          error_code='consumer_grant_revoked_before_execution',
          completed_at=now(),updated_at=now()
        where id=v_job.id and status='queued';
        v_queued_cancelled := v_queued_cancelled + 1;
      exception when others then
        begin
          perform public.credit_ledger_mark_pending(jsonb_build_object(
            'reservation_id',v_job.reservation_id,
            'reason_code','consumer_grant_revocation_release_requires_reconciliation'
          ));
        exception when others then
          null;
        end;
        update public.generation_jobs set status='pending_reconciliation',
          error_code='consumer_grant_revocation_release_requires_reconciliation',
          completed_at=now(),lease_token=null,lease_expires_at=null,updated_at=now()
        where id=v_job.id and status='queued';
      end;
    else
      begin
        perform public.credit_ledger_mark_pending(jsonb_build_object(
          'reservation_id',v_job.reservation_id,
          'reason_code','consumer_grant_revoked_failure_release_not_approved'
        ));
      exception when others then
        null;
      end;
      update public.generation_jobs set status='pending_reconciliation',
        error_code='consumer_grant_revoked_failure_release_not_approved',
        completed_at=now(),updated_at=now()
      where id=v_job.id and status='queued';
    end if;
  end loop;

  -- A running job may already have reached the provider. Never release its
  -- reservation or replay it based only on a grant revocation.
  for v_job in
    select id,reservation_id
    from public.generation_jobs
    where consumer_grant_id=v_grant.id and status='running'
    for update
  loop
    begin
      perform public.credit_ledger_mark_pending(jsonb_build_object(
        'reservation_id',v_job.reservation_id,
        'reason_code','consumer_grant_revoked_provider_outcome_unknown'
      ));
    exception when others then
      null;
    end;
    update public.generation_jobs set status='pending_reconciliation',
      error_code='consumer_grant_revoked_provider_outcome_unknown',
      lease_token=null,lease_expires_at=null,updated_at=now()
    where id=v_job.id and status='running';
    v_running_reconciled := v_running_reconciled + 1;
  end loop;

  if not v_already_revoked then
    insert into public.agent_consumer_grant_events(
      grant_id,requester_user_id,owner_user_id,agent_id,actor_user_id,
      event_type,reason_code,details
    ) values (
      v_grant.id,v_grant.requester_user_id,v_grant.owner_user_id,v_grant.agent_id,
      p_owner_user_id,'revoked',v_reason,
      jsonb_build_object('queued_cancelled',v_queued_cancelled,
        'running_pending_reconciliation',v_running_reconciled)
    );
  end if;

  return jsonb_build_object(
    'grant_id',v_grant.id,'status',v_grant.status,'revoked_at',v_grant.revoked_at,
    'queued_cancelled',v_queued_cancelled,
    'running_pending_reconciliation',v_running_reconciled,
    'already_revoked',v_already_revoked
  );
end;
$$;

revoke all on function public.agent_consumer_grant_revoke(uuid,uuid,text)
  from public,anon,authenticated;
grant execute on function public.agent_consumer_grant_revoke(uuid,uuid,text)
  to service_role;

comment on table public.agent_consumer_grant_events is
  'Append-only audit of external Agent Consumer grant creation, revocation and affected generation lifecycle.';
comment on function public.agent_consumer_grant_revoke(uuid,uuid,text) is
  'Atomically revokes an owner grant, releases eligible queued reservations, and fences running jobs into reconciliation.';

commit;
