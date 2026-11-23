-- ENG-P04: owner-controlled Passion/Habit signals and one shared scoring policy.
-- Passion is explicit-only; Habit may use observed interactions only while personalization is enabled.
-- Neither signal is indexed for public discovery or exposed to other users.

create table if not exists public.user_interest_graph_signals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid references public.ai_agents(id) on delete cascade,
  interest_key text not null references public.interest_catalog(interest_key) on delete cascade,
  signal_type text not null check (signal_type in ('passion','habit')),
  strength numeric(4,3) not null check (strength >= 0 and strength <= 1),
  signal_source text not null check (signal_source in ('user_selected','explicit_feedback','observed_interaction')),
  consent_version text not null check (consent_version = 'interest-graph-v1'),
  consent_granted_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint passion_never_inferred check (signal_type <> 'passion' or signal_source <> 'observed_interaction')
);
create unique index if not exists user_interest_graph_signals_subject_unique
  on public.user_interest_graph_signals(user_id,agent_id,interest_key,signal_type)
  nulls not distinct;
create index if not exists user_interest_graph_signals_owner_type_idx
  on public.user_interest_graph_signals(user_id,signal_type,updated_at desc);

alter table public.user_interest_graph_signals enable row level security;
drop policy if exists user_interest_graph_signals_select_self on public.user_interest_graph_signals;
create policy user_interest_graph_signals_select_self on public.user_interest_graph_signals
for select to authenticated using (user_id=(select auth.uid()));
revoke all privileges on public.user_interest_graph_signals from public,anon,authenticated;
grant select on public.user_interest_graph_signals to authenticated;
grant select,insert,update,delete on public.user_interest_graph_signals to service_role;

create table if not exists public.user_interest_graph_signal_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid references public.ai_agents(id) on delete cascade,
  interest_key text not null,
  signal_type text not null check (signal_type in ('passion','habit')),
  action text not null check (action in ('set','delete','reset')),
  signal_source text,
  consent_version text,
  occurred_at timestamptz not null default now()
);
create index if not exists user_interest_graph_signal_events_owner_idx
  on public.user_interest_graph_signal_events(user_id,occurred_at desc);
alter table public.user_interest_graph_signal_events enable row level security;
drop policy if exists user_interest_graph_signal_events_select_self on public.user_interest_graph_signal_events;
create policy user_interest_graph_signal_events_select_self on public.user_interest_graph_signal_events
for select to authenticated using (user_id=(select auth.uid()));
revoke all privileges on public.user_interest_graph_signal_events from public,anon,authenticated;
grant select on public.user_interest_graph_signal_events to authenticated;
grant select,insert on public.user_interest_graph_signal_events to service_role;

create table if not exists public.recommendation_scoring_policies (
  policy_key text primary key,
  version text not null check (char_length(version) between 1 and 80),
  weights jsonb not null check (jsonb_typeof(weights)='object'),
  active boolean not null default false,
  updated_at timestamptz not null default now()
);
insert into public.recommendation_scoring_policies(policy_key,version,weights,active)
values ('default','allpha-recommendation-v2',
  '{"followed_creator":1000.0,"explicit_interest":100.0,"passion":25.0,"habit":10.0,"engagement":1.0,"mutual_connection":2.0,"shared_interest":3.0}'::jsonb,
  true)
on conflict(policy_key) do nothing;
create unique index if not exists recommendation_scoring_one_active_policy
  on public.recommendation_scoring_policies(active) where active;
alter table public.recommendation_scoring_policies enable row level security;
revoke all privileges on public.recommendation_scoring_policies from public,anon,authenticated;
grant select,insert,update,delete on public.recommendation_scoring_policies to service_role;

create or replace function public.set_user_interest_graph_signal_for_actor(
  p_actor_user_id uuid,
  p_interest_key text,
  p_signal_type text,
  p_strength numeric,
  p_signal_source text,
  p_consent_version text,
  p_agent_id uuid default null
)
returns table(user_id uuid,agent_id uuid,interest_key text,signal_type text,strength numeric,signal_source text,consent_version text,consent_granted_at timestamptz,created_at timestamptz,updated_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $set_interest_signal$
declare
  v_key text;
  v_sensitivity text;
  v_personalization_enabled boolean;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null or not exists(select 1 from auth.users u where u.id=p_actor_user_id) then
    raise exception 'interest_signal_actor_not_found' using errcode='P0002';
  end if;
  if p_signal_type is null or p_signal_type not in ('passion','habit')
     or p_signal_source is null or p_signal_source not in ('user_selected','explicit_feedback','observed_interaction')
     or p_strength is null or p_strength < 0 or p_strength > 1
     or p_consent_version is null or char_length(p_consent_version) not between 1 and 80 then
    raise exception 'interest_signal_invalid' using errcode='22023';
  end if;
  if p_signal_type='passion' and p_signal_source='observed_interaction' then
    raise exception 'passion_signal_requires_explicit_user_input' using errcode='42501';
  end if;
  if p_agent_id is not null and not exists(
    select 1 from public.agent_ownerships o
    join public.ai_agents a on a.id=o.agent_id
    where o.agent_id=p_agent_id and o.owner_user_id=p_actor_user_id
      and o.ownership_role='owner' and o.status='active' and a.status='active'
  ) then
    raise exception 'interest_agent_ownership_required' using errcode='42501';
  end if;
  if p_signal_source='observed_interaction' then
    select coalesce(fp.personalization_enabled,false) into v_personalization_enabled
      from public.feed_preferences fp where fp.user_id=p_actor_user_id;
    if coalesce(v_personalization_enabled,false) is not true then
      raise exception 'personalization_consent_required' using errcode='42501';
    end if;
  end if;
  select c.interest_key,c.sensitivity into v_key,v_sensitivity
    from public.interest_catalog c
   where c.active and (
     lower(c.interest_key)=lower(p_interest_key)
     or exists(select 1 from unnest(c.aliases) a where lower(a)=lower(p_interest_key))
   )
   order by case when lower(c.interest_key)=lower(p_interest_key) then 0 else 1 end
   limit 1;
  if v_key is null then
    raise exception 'interest_key_not_in_catalog' using errcode='22023';
  end if;
  if p_signal_source='observed_interaction' and v_sensitivity='sensitive' then
    raise exception 'interest_sensitive_inference_prohibited' using errcode='42501';
  end if;
  return query
  insert into public.user_interest_graph_signals as s(
    user_id,agent_id,interest_key,signal_type,strength,signal_source,consent_version,consent_granted_at
  ) values (
    p_actor_user_id,p_agent_id,v_key,p_signal_type,p_strength,p_signal_source,p_consent_version,pg_catalog.now()
  )
  on conflict(user_id,agent_id,interest_key,signal_type) do update
    set strength=excluded.strength,signal_source=excluded.signal_source,
        consent_version=excluded.consent_version,consent_granted_at=excluded.consent_granted_at,
        updated_at=pg_catalog.now()
  returning s.user_id,s.agent_id,s.interest_key,s.signal_type,s.strength,s.signal_source,
    s.consent_version,s.consent_granted_at,s.created_at,s.updated_at;
  insert into public.user_interest_graph_signal_events(user_id,agent_id,interest_key,signal_type,action,signal_source,consent_version)
  values(p_actor_user_id,p_agent_id,v_key,p_signal_type,'set',p_signal_source,p_consent_version);
end;
$set_interest_signal$;

create or replace function public.delete_user_interest_graph_signal_for_actor(
  p_actor_user_id uuid,p_interest_key text,p_signal_type text,p_agent_id uuid default null
)
returns table(interest_key text,signal_type text,agent_id uuid)
language plpgsql
security definer
set search_path = ''
as $delete_interest_signal$
declare v_key text;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null or not exists(select 1 from auth.users u where u.id=p_actor_user_id)
     or p_signal_type is null or p_signal_type not in ('passion','habit') then
    raise exception 'interest_signal_actor_or_type_invalid' using errcode='22023';
  end if;
  select c.interest_key into v_key from public.interest_catalog c
   where c.active and (lower(c.interest_key)=lower(p_interest_key)
      or exists(select 1 from unnest(c.aliases) a where lower(a)=lower(p_interest_key)))
   order by case when lower(c.interest_key)=lower(p_interest_key) then 0 else 1 end limit 1;
  if v_key is null then raise exception 'interest_key_not_in_catalog' using errcode='P0002'; end if;
  return query delete from public.user_interest_graph_signals s
   where s.user_id=p_actor_user_id and s.agent_id is not distinct from p_agent_id
     and s.interest_key=v_key and s.signal_type=p_signal_type
   returning s.interest_key,s.signal_type,s.agent_id;
  if found then
    insert into public.user_interest_graph_signal_events(user_id,agent_id,interest_key,signal_type,action)
    values(p_actor_user_id,p_agent_id,v_key,p_signal_type,'delete');
  end if;
end;
$delete_interest_signal$;

create or replace function public.clear_user_interest_graph_signals_for_actor(p_actor_user_id uuid)
returns integer
language plpgsql
security definer
set search_path = ''
as $clear_interest_signals$
declare v_count integer;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null or not exists(select 1 from auth.users u where u.id=p_actor_user_id) then
    raise exception 'interest_signal_actor_not_found' using errcode='P0002';
  end if;
  with deleted as (
    delete from public.user_interest_graph_signals s where s.user_id=p_actor_user_id
    returning s.user_id,s.agent_id,s.interest_key,s.signal_type,s.signal_source,s.consent_version
  )
  insert into public.user_interest_graph_signal_events(user_id,agent_id,interest_key,signal_type,action,signal_source,consent_version)
  select user_id,agent_id,interest_key,signal_type,'reset',signal_source,consent_version from deleted;
  get diagnostics v_count=row_count;
  return v_count;
end;
$clear_interest_signals$;

revoke all on function public.set_user_interest_graph_signal_for_actor(uuid,text,text,numeric,text,text,uuid) from public,anon,authenticated;
revoke all on function public.delete_user_interest_graph_signal_for_actor(uuid,text,text,uuid) from public,anon,authenticated;
revoke all on function public.clear_user_interest_graph_signals_for_actor(uuid) from public,anon,authenticated;
grant execute on function public.set_user_interest_graph_signal_for_actor(uuid,text,text,numeric,text,text,uuid) to service_role;
grant execute on function public.delete_user_interest_graph_signal_for_actor(uuid,text,text,uuid) to service_role;
grant execute on function public.clear_user_interest_graph_signals_for_actor(uuid) to service_role;


-- Export Passion/Habit state and immutable change history with the account archive.
insert into private.account_export_sources(source_key,table_name,filter_kind,owner_columns,sort_order)
values
  ('interest_graph_signals','user_interest_graph_signals','owner_columns',array['user_id'],44),
  ('interest_graph_signal_events','user_interest_graph_signal_events','owner_columns',array['user_id'],45)
on conflict (source_key) do nothing;

-- Turning off feed personalization removes observed Habit signals for both
-- the Human and any owned Agent; explicit Passion selections remain intact.
create or replace function private.purge_observed_interest_signals_on_opt_out()
returns trigger
language plpgsql
security definer
set search_path = ''
as $purge_observed_signals$
begin
  if old.personalization_enabled is distinct from new.personalization_enabled
     and new.personalization_enabled is false then
    with deleted as (
      delete from public.user_interest_graph_signals s
       where s.user_id=new.user_id and s.signal_source='observed_interaction'
      returning s.user_id,s.agent_id,s.interest_key,s.signal_type,s.signal_source,s.consent_version
    )
    insert into public.user_interest_graph_signal_events(
      user_id,agent_id,interest_key,signal_type,action,signal_source,consent_version
    )
    select user_id,agent_id,interest_key,signal_type,'delete',signal_source,consent_version from deleted;
  end if;
  return new;
end;
$purge_observed_signals$;

drop trigger if exists feed_preferences_purge_observed_interest_signals on public.feed_preferences;
create trigger feed_preferences_purge_observed_interest_signals
after update of personalization_enabled on public.feed_preferences
for each row execute function private.purge_observed_interest_signals_on_opt_out();
revoke all on function private.purge_observed_interest_signals_on_opt_out() from public,anon,authenticated;
