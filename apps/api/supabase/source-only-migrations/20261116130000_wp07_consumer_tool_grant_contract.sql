-- WP-07 explicit per-tool External Consumer grant contract.
-- Private Memory remains unavailable to Consumers. This migration only records
-- the exact deterministic tool allowlist approved by the Agent owner.
begin;

alter table public.agent_consumer_grants
  add column if not exists allowed_tool_keys text[] not null default '{}'::text[],
  add column if not exists max_tool_calls integer not null default 0,
  add column if not exists max_tool_runtime_seconds integer not null default 0;

alter table public.agent_consumer_grants
  drop constraint if exists agent_consumer_grant_scopes;
alter table public.agent_consumer_grants
  add constraint agent_consumer_grant_scopes check (
    cardinality(granted_scopes) > 0
    and granted_scopes <@ array[
      'public_invoke','generation_invoke','knowledge_public_read','tool_invoke'
    ]::text[]
    and (not ('knowledge_public_read' = any(granted_scopes))
      or 'generation_invoke' = any(granted_scopes))
    and (not ('tool_invoke' = any(granted_scopes))
      or 'generation_invoke' = any(granted_scopes))
  );

alter table public.agent_consumer_grants
  drop constraint if exists agent_consumer_grant_tool_scope_contract;
alter table public.agent_consumer_grants
  add constraint agent_consumer_grant_tool_scope_contract check (
    cardinality(allowed_tool_keys) <= 5
    and (
      ('tool_invoke' = any(granted_scopes)
        and cardinality(allowed_tool_keys) between 1 and 5
        and max_tool_calls between 1 and 5
        and max_tool_runtime_seconds between 1 and 30)
      or
      (not ('tool_invoke' = any(granted_scopes))
        and cardinality(allowed_tool_keys) = 0
        and max_tool_calls = 0
        and max_tool_runtime_seconds = 0)
    )
  );

create or replace function public.validate_agent_consumer_grant_tool_keys()
returns trigger language plpgsql set search_path = '' as $$
declare
  v_count integer;
  v_distinct_count integer;
begin
  if cardinality(new.allowed_tool_keys) > 5 then
    raise exception 'CONSUMER_TOOL_ALLOWLIST_TOO_LARGE' using errcode='22023';
  end if;
  if exists (
    select 1 from unnest(new.allowed_tool_keys) as item(tool_key)
    where tool_key !~ '^[a-z][a-z0-9_.:-]+$'
  ) then
    raise exception 'CONSUMER_TOOL_ALLOWLIST_INVALID' using errcode='22023';
  end if;
  select count(*), count(distinct tool_key)
    into v_count, v_distinct_count
  from unnest(new.allowed_tool_keys) as item(tool_key);
  if v_count <> v_distinct_count then
    raise exception 'CONSUMER_TOOL_ALLOWLIST_DUPLICATE' using errcode='22023';
  end if;
  return new;
end;
$$;

drop trigger if exists agent_consumer_grant_tool_keys_validate on public.agent_consumer_grants;
create trigger agent_consumer_grant_tool_keys_validate
before insert or update of allowed_tool_keys, granted_scopes
on public.agent_consumer_grants
for each row execute function public.validate_agent_consumer_grant_tool_keys();

revoke all on function public.validate_agent_consumer_grant_tool_keys()
  from public, anon, authenticated, service_role;
grant execute on function public.validate_agent_consumer_grant_tool_keys()
  to service_role;

create or replace function public.guard_external_generation_tool_grant()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
  v_grant public.agent_consumer_grants;
  v_dependencies text[] := '{}'::text[];
  v_skill_budget jsonb := '{}'::jsonb;
  v_skill_max_calls integer := 1;
  v_skill_max_runtime integer := 30;
begin
  if new.consumer_grant_id is null then
    return new;
  end if;

  if jsonb_typeof(coalesce(new.skill_snapshot->'tool_dependencies','[]'::jsonb)) <> 'array' then
    raise exception 'GENERATION_SKILL_TOOL_DEPENDENCIES_INVALID' using errcode='22023';
  end if;
  select coalesce(array_agg(value), '{}'::text[])
    into v_dependencies
  from jsonb_array_elements_text(coalesce(new.skill_snapshot->'tool_dependencies','[]'::jsonb)) as item(value);

  select * into v_grant
  from public.agent_consumer_grants
  where id = new.consumer_grant_id
  for share;
  if not found or v_grant.status <> 'active'
    or not ('generation_invoke' = any(v_grant.granted_scopes)) then
    raise exception 'GENERATION_CONSUMER_GRANT_INVALID' using errcode='42501';
  end if;

  if cardinality(v_dependencies) > 0 then
    v_skill_budget := coalesce(new.skill_snapshot->'budget_limits', '{}'::jsonb);
    v_skill_max_calls := coalesce((v_skill_budget->>'max_tool_calls')::integer, 1);
    v_skill_max_runtime := coalesce((v_skill_budget->>'max_runtime_seconds')::integer, 30);
    if not ('tool_invoke' = any(v_grant.granted_scopes))
      or cardinality(v_grant.allowed_tool_keys) <> cardinality(v_dependencies)
      or not (v_grant.allowed_tool_keys @> v_dependencies)
      or not (v_dependencies @> v_grant.allowed_tool_keys)
      or v_grant.max_tool_calls < cardinality(v_dependencies)
      or v_grant.max_tool_calls > least(5, v_skill_max_calls)
      or v_grant.max_tool_runtime_seconds > least(30, v_skill_max_runtime) then
      raise exception 'GENERATION_CONSUMER_TOOL_GRANT_REQUIRED' using errcode='42501';
    end if;
  elsif 'tool_invoke' = any(v_grant.granted_scopes)
    or cardinality(v_grant.allowed_tool_keys) <> 0
    or v_grant.max_tool_calls <> 0
    or v_grant.max_tool_runtime_seconds <> 0 then
    raise exception 'GENERATION_CONSUMER_TOOL_GRANT_NOT_NEEDED' using errcode='22023';
  end if;

  return new;
end;
$$;

drop trigger if exists generation_jobs_consumer_tool_grant_insert on public.generation_jobs;
create trigger generation_jobs_consumer_tool_grant_insert
before insert on public.generation_jobs
for each row execute function public.guard_external_generation_tool_grant();

drop trigger if exists generation_jobs_consumer_tool_grant_update on public.generation_jobs;
create trigger generation_jobs_consumer_tool_grant_update
before update of consumer_grant_id, skill_snapshot on public.generation_jobs
for each row execute function public.guard_external_generation_tool_grant();

revoke all on function public.guard_external_generation_tool_grant()
  from public, anon, authenticated, service_role;
grant execute on function public.guard_external_generation_tool_grant()
  to service_role;

create or replace function public.audit_agent_consumer_grant_created()
returns trigger language plpgsql security definer set search_path = '' as $$
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
      'granted_scopes',new.granted_scopes,'allowed_tool_keys',new.allowed_tool_keys,
      'max_tool_calls',new.max_tool_calls,'max_tool_runtime_seconds',new.max_tool_runtime_seconds,
      'capability_id',new.capability_id,
      'credit_scheme_version',new.credit_scheme_version,'tariff_version',new.tariff_version,
      'entitlement_version',new.entitlement_version,'payer_role',new.payer_role,
      'expires_at',new.expires_at
    )
  );
  return new;
end;
$$;

revoke all on function public.audit_agent_consumer_grant_created()
  from public, anon, authenticated;
grant execute on function public.audit_agent_consumer_grant_created()
  to service_role;

comment on column public.agent_consumer_grants.allowed_tool_keys is
  'Exact owner-approved allowlist for tool_invoke. Must match the pinned Skill dependency set for external Generation; no private Memory permission is represented here.';
comment on column public.agent_consumer_grants.max_tool_calls is
  'Owner-approved per-grant maximum number of deterministic tool calls; zero unless tool_invoke is explicitly granted.';
comment on column public.agent_consumer_grants.max_tool_runtime_seconds is
  'Owner-approved per-grant maximum tool runtime seconds; zero unless tool_invoke is explicitly granted.';
comment on function public.guard_external_generation_tool_grant() is
  'Rejects external Generation jobs whose pinned Skill tool dependencies do not exactly match the active Consumer grant allowlist.';

commit;
