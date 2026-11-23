-- ENG-P04 forward migration: normalized interest ontology and opt-in discovery index.
-- Interest preferences remain owner-readable. The discovery index contains only
-- interests whose owner explicitly opted into interest matching and public discovery.

create table if not exists public.interest_catalog (
  interest_key text primary key check (interest_key ~ '^[a-z0-9][a-z0-9._-]{0,79}$'),
  label text not null check (char_length(label) between 1 and 80),
  label_key text not null check (char_length(label_key) between 1 and 100),
  category text not null check (char_length(category) between 1 and 60),
  aliases text[] not null default '{}',
  active boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.interest_catalog(interest_key,label,label_key,category,aliases,active,sort_order)
values
  ('health','Kesehatan','auth.interest.health','wellbeing',array['Kesehatan'],true,10),
  ('technology','IT & Teknologi','auth.interest.tech','technology',array['IT & Teknologi','Teknologi'],true,20),
  ('spatial_3d','3D Spatial','auth.interest.spatial','spatial',array['3D Spatial','3D'],true,30),
  ('content_creator','Kreator Konten','auth.interest.creator','creator',array['Kreator Konten','Konten Kreator'],true,40),
  ('business_finance','Bisnis & Finansial','auth.interest.businessFinance','business',array['Bisnis & Finansial','Bisnis dan Finansial'],true,50),
  ('design_ui_ux','Desain & UI/UX','auth.interest.designUi','design',array['Desain & UI/UX','Desain'],true,60),
  ('education_research','Edukasi & Riset','auth.interest.education','education',array['Edukasi & Riset','Edukasi'],true,70),
  ('gaming_metaverse','Gaming & Metaverse','auth.interest.metaverse','gaming',array['Gaming & Metaverse','Gaming'],true,80)
on conflict (interest_key) do update set
  label=excluded.label,label_key=excluded.label_key,category=excluded.category,
  aliases=excluded.aliases,active=excluded.active,sort_order=excluded.sort_order,updated_at=now();

alter table public.interest_catalog enable row level security;
drop policy if exists interest_catalog_read_active on public.interest_catalog;
create policy interest_catalog_read_active on public.interest_catalog
for select to anon,authenticated using (active=true);
revoke all privileges on public.interest_catalog from anon,authenticated;
grant select on public.interest_catalog to anon,authenticated;
grant select,insert,update,delete on public.interest_catalog to service_role;

alter table public.user_settings alter column privacy_settings
  set default '{"discoverable_by_username":true,"allow_interest_matching":false}'::jsonb;
update public.user_settings
   set privacy_settings=jsonb_set(coalesce(privacy_settings,'{}'::jsonb),'{allow_interest_matching}','false'::jsonb,true)
 where not (coalesce(privacy_settings,'{}'::jsonb) ? 'allow_interest_matching');

create table if not exists private.user_interest_discovery_index (
  user_id uuid not null references auth.users(id) on delete cascade,
  interest_key text not null references public.interest_catalog(interest_key) on delete cascade,
  indexed_at timestamptz not null default now(),
  primary key(user_id,interest_key)
);
create index if not exists user_interest_discovery_index_interest_idx
  on private.user_interest_discovery_index(interest_key,user_id);
revoke all privileges on private.user_interest_discovery_index from public,anon,authenticated;
grant select,insert,update,delete on private.user_interest_discovery_index to service_role;

create or replace function private.refresh_user_interest_discovery_index(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $refresh_interest_index$
begin
  delete from private.user_interest_discovery_index where user_id=p_user_id;
  if exists (
    select 1 from public.user_settings s
     where s.user_id=p_user_id
       and coalesce(s.privacy_settings,'{}'::jsonb) @> '{"discoverable_by_username":true,"allow_interest_matching":true}'::jsonb
       and exists (
         select 1 from public.profiles p
          where p.id=p_user_id and p.visibility='public' and p.account_status='active'
       )
  ) then
    insert into private.user_interest_discovery_index(user_id,interest_key)
    select ui.user_id,ui.interest_key
      from public.user_interests ui
      join public.interest_catalog c on c.interest_key=ui.interest_key and c.active=true
     where ui.user_id=p_user_id and ui.preference='interested'
    on conflict (user_id,interest_key) do update set indexed_at=now();
  end if;
end;
$refresh_interest_index$;

create or replace function private.refresh_interest_index_from_user_interests()
returns trigger
language plpgsql
security definer
set search_path = ''
as $refresh_interest_trigger$
begin
  if tg_op='DELETE' then
    perform private.refresh_user_interest_discovery_index(old.user_id);
    return old;
  end if;
  perform private.refresh_user_interest_discovery_index(new.user_id);
  if tg_op='UPDATE' and old.user_id is distinct from new.user_id then
    perform private.refresh_user_interest_discovery_index(old.user_id);
  end if;
  return new;
end;
$refresh_interest_trigger$;

create or replace function private.refresh_interest_index_from_user_settings()
returns trigger
language plpgsql
security definer
set search_path = ''
as $refresh_settings_trigger$
begin
  perform private.refresh_user_interest_discovery_index(new.user_id);
  return new;
end;
$refresh_settings_trigger$;

drop trigger if exists user_interests_refresh_discovery_index on public.user_interests;
create trigger user_interests_refresh_discovery_index
after insert or update or delete on public.user_interests
for each row execute function private.refresh_interest_index_from_user_interests();

drop trigger if exists user_settings_refresh_discovery_index on public.user_settings;
create trigger user_settings_refresh_discovery_index
after insert or update of privacy_settings on public.user_settings
for each row execute function private.refresh_interest_index_from_user_settings();

create or replace function public.set_my_interest_preference_for_actor(
  p_actor_user_id uuid,
  p_interest_key text,
  p_preference text
)
returns table(interest_key text,preference text,created_at timestamptz,updated_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $set_interest$
declare
  v_interest_key text;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null or not exists(select 1 from auth.users u where u.id=p_actor_user_id) then
    raise exception 'interest_actor_not_found' using errcode='P0002';
  end if;
  if p_preference is null or p_preference not in ('interested','not_interested') then
    raise exception 'interest_preference_invalid' using errcode='22023';
  end if;
  select c.interest_key into v_interest_key
    from public.interest_catalog c
   where c.active=true
     and (lower(c.interest_key)=lower(p_interest_key)
       or exists(select 1 from unnest(c.aliases) a where lower(a)=lower(p_interest_key)))
   order by case when lower(c.interest_key)=lower(p_interest_key) then 0 else 1 end
   limit 1;
  if v_interest_key is null then
    -- Preserve preference updates for a user's pre-catalog legacy keys, but do
    -- not permit creating new arbitrary keys outside the canonical ontology.
    if exists(select 1 from public.user_interests ui where ui.user_id=p_actor_user_id and ui.interest_key=p_interest_key) then
      v_interest_key := p_interest_key;
    else
      raise exception 'interest_key_not_in_catalog' using errcode='22023';
    end if;
  end if;
  return query
  insert into public.user_interests as ui(user_id,interest_key,preference)
  values(p_actor_user_id,v_interest_key,p_preference)
  on conflict(user_id,interest_key) do update
    set preference=excluded.preference,updated_at=now()
  returning ui.interest_key,ui.preference,ui.created_at,ui.updated_at;
end;
$set_interest$;

create or replace function public.delete_my_interest_for_actor(
  p_actor_user_id uuid,
  p_interest_key text
)
returns table(interest_key text)
language plpgsql
security definer
set search_path = ''
as $delete_interest$
declare
  v_interest_key text;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null or not exists(select 1 from auth.users u where u.id=p_actor_user_id) then
    raise exception 'interest_actor_not_found' using errcode='P0002';
  end if;
  select c.interest_key into v_interest_key
    from public.interest_catalog c
   where c.active=true
     and (lower(c.interest_key)=lower(p_interest_key)
       or exists(select 1 from unnest(c.aliases) a where lower(a)=lower(p_interest_key)))
   order by case when lower(c.interest_key)=lower(p_interest_key) then 0 else 1 end
   limit 1;
  if v_interest_key is null then
    -- Existing custom/legacy keys remain removable after the catalog cutover.
    if exists(select 1 from public.user_interests ui where ui.user_id=p_actor_user_id and ui.interest_key=p_interest_key) then
      v_interest_key := p_interest_key;
    else
      raise exception 'interest_key_not_found' using errcode='P0002';
    end if;
  end if;
  return query delete from public.user_interests ui
   where ui.user_id=p_actor_user_id and ui.interest_key=v_interest_key
   returning ui.interest_key;
end;
$delete_interest$;

create or replace function public.find_interest_discovery_candidates(
  p_interest_keys text[],
  p_limit integer default 500
)
returns table(user_id uuid,interest_key text)
language plpgsql
security definer
set search_path = ''
as $find_interest_candidates$
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_interest_keys is null or cardinality(p_interest_keys)=0
     or p_limit is null or p_limit not between 1 and 5000 then
    raise exception 'interest_discovery_query_invalid' using errcode='22023';
  end if;
  return query
  select i.user_id,i.interest_key
    from private.user_interest_discovery_index i
    join public.interest_catalog c on c.interest_key=i.interest_key and c.active=true
   where i.interest_key=any(p_interest_keys)
   order by i.interest_key,i.user_id
   limit p_limit;
end;
$find_interest_candidates$;

revoke all on function private.refresh_user_interest_discovery_index(uuid) from public,anon,authenticated;
revoke all on function private.refresh_interest_index_from_user_interests() from public,anon,authenticated;
revoke all on function private.refresh_interest_index_from_user_settings() from public,anon,authenticated;
revoke all on function public.set_my_interest_preference_for_actor(uuid,text,text) from public,anon,authenticated;
revoke all on function public.delete_my_interest_for_actor(uuid,text) from public,anon,authenticated;
revoke all on function public.find_interest_discovery_candidates(text[],integer) from public,anon,authenticated;
grant execute on function public.set_my_interest_preference_for_actor(uuid,text,text) to service_role;
grant execute on function public.delete_my_interest_for_actor(uuid,text) to service_role;
grant execute on function public.find_interest_discovery_candidates(text[],integer) to service_role;

revoke insert,update,delete on public.user_interests from anon,authenticated;
grant select on public.user_interests to authenticated;
grant select,insert,update,delete on public.user_interests to service_role;


-- One canonical Interest Graph signal store. A signal may describe the
-- authenticated Human or one of that Human's actively owned AI Agents.
create table if not exists public.user_interest_graph_signals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid references public.ai_agents(id) on delete cascade,
  interest_key text not null references public.interest_catalog(interest_key) on delete restrict,
  signal_type text not null check (signal_type in ('passion','habit')),
  strength numeric(4,3) not null check (strength between 0 and 1),
  signal_source text not null check (signal_source in ('user_selected','explicit_feedback','observed_interaction')),
  consent_version text not null check (consent_version = 'interest-graph-v1'),
  consent_granted_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists user_interest_graph_signals_subject_unique
  on public.user_interest_graph_signals(user_id,agent_id,interest_key,signal_type)
  nulls not distinct;
create index if not exists user_interest_graph_signals_owner_idx
  on public.user_interest_graph_signals(user_id,signal_type,interest_key);
create index if not exists user_interest_graph_signals_agent_idx
  on public.user_interest_graph_signals(agent_id,signal_type,interest_key)
  where agent_id is not null;

create table if not exists public.user_interest_graph_signal_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid references public.ai_agents(id) on delete cascade,
  interest_key text,
  signal_type text check (signal_type is null or signal_type in ('passion','habit')),
  action text not null check (action in ('set','delete','reset')),
  signal_source text check (signal_source is null or signal_source in ('user_selected','explicit_feedback','observed_interaction')),
  consent_version text not null check (consent_version = 'interest-graph-v1'),
  occurred_at timestamptz not null default now()
);
create index if not exists user_interest_graph_signal_events_owner_idx
  on public.user_interest_graph_signal_events(user_id,occurred_at desc);

alter table public.user_interest_graph_signals enable row level security;
alter table public.user_interest_graph_signal_events enable row level security;
drop policy if exists user_interest_graph_signals_select_self on public.user_interest_graph_signals;
create policy user_interest_graph_signals_select_self on public.user_interest_graph_signals
for select to authenticated using (user_id=(select auth.uid()));
drop policy if exists user_interest_graph_signal_events_select_self on public.user_interest_graph_signal_events;
create policy user_interest_graph_signal_events_select_self on public.user_interest_graph_signal_events
for select to authenticated using (user_id=(select auth.uid()));
revoke all privileges on public.user_interest_graph_signals,public.user_interest_graph_signal_events from public,anon,authenticated;
grant select on public.user_interest_graph_signals,public.user_interest_graph_signal_events to authenticated;
grant select,insert,update,delete on public.user_interest_graph_signals,public.user_interest_graph_signal_events to service_role;

-- Include user-controlled Passion/Habit graph signals in the account export.
insert into private.account_export_sources(source_key,table_name,filter_kind,owner_columns,sort_order)
values
  ('interest_graph_signals','user_interest_graph_signals','owner_columns',array['user_id'],44),
  ('interest_graph_signal_events','user_interest_graph_signal_events','owner_columns',array['user_id'],45)
on conflict (source_key) do nothing;

create table if not exists public.recommendation_scoring_policies (
  id uuid primary key default gen_random_uuid(),
  policy_key text not null,
  version text not null,
  weights jsonb not null check (jsonb_typeof(weights)='object'),
  active boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(policy_key,version)
);
create unique index if not exists recommendation_scoring_one_active_policy
  on public.recommendation_scoring_policies(policy_key) where active;
alter table public.recommendation_scoring_policies enable row level security;
revoke all privileges on public.recommendation_scoring_policies from public,anon,authenticated;
grant select,insert,update,delete on public.recommendation_scoring_policies to service_role;
insert into public.recommendation_scoring_policies(policy_key,version,weights,active)
values ('default','allpha-recommendation-v2',
  '{"followed_creator":1000,"explicit_interest":100,"passion":25,"habit":10,"engagement":1,"mutual_connection":2,"shared_interest":3}'::jsonb,
  true)
on conflict (policy_key,version) do nothing;

create or replace function public.set_user_interest_graph_signal_for_actor(
  p_actor_user_id uuid,
  p_interest_key text,
  p_signal_type text,
  p_strength numeric,
  p_signal_source text,
  p_consent_version text,
  p_agent_id uuid default null
)
returns table(
  user_id uuid,agent_id uuid,interest_key text,signal_type text,strength numeric,
  signal_source text,consent_version text,consent_granted_at timestamptz,
  created_at timestamptz,updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $set_interest_signal$
declare
  v_interest_key text;
  v_signal public.user_interest_graph_signals%rowtype;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null or not exists(select 1 from auth.users u where u.id=p_actor_user_id) then
    raise exception 'interest_actor_not_found' using errcode='P0002';
  end if;
  if p_signal_type is null or p_signal_type not in ('passion','habit')
     or p_strength is null or p_strength < 0 or p_strength > 1
     or p_signal_source is null or p_signal_source not in ('user_selected','explicit_feedback','observed_interaction')
     or p_consent_version is distinct from 'interest-graph-v1' then
    raise exception 'interest_signal_input_invalid' using errcode='22023';
  end if;
  if p_agent_id is not null and not exists(
    select 1 from public.agent_ownerships o
    join public.ai_agents a on a.id=o.agent_id
    where o.agent_id=p_agent_id and o.owner_user_id=p_actor_user_id
      and o.ownership_role='owner' and o.status='active' and a.status='active'
  ) then
    raise exception 'interest_agent_ownership_required' using errcode='42501';
  end if;
  if p_signal_source='observed_interaction' and not exists(
    select 1 from public.user_settings s
    where s.user_id=p_actor_user_id
      and coalesce(s.privacy_settings,'{}'::jsonb) @> '{"allow_interest_matching":true}'::jsonb
  ) then
    raise exception 'interest_observation_consent_required' using errcode='42501';
  end if;
  select c.interest_key into v_interest_key
    from public.interest_catalog c
   where c.active and (
     lower(c.interest_key)=lower(p_interest_key)
     or exists(select 1 from unnest(c.aliases) a where lower(a)=lower(p_interest_key))
   )
   order by case when lower(c.interest_key)=lower(p_interest_key) then 0 else 1 end
   limit 1;
  if v_interest_key is null then
    raise exception 'interest_key_not_in_catalog' using errcode='22023';
  end if;

  insert into public.user_interest_graph_signals as s(
    user_id,agent_id,interest_key,signal_type,strength,signal_source,consent_version,consent_granted_at
  ) values (
    p_actor_user_id,p_agent_id,v_interest_key,p_signal_type,p_strength,p_signal_source,
    p_consent_version,now()
  )
  on conflict (user_id,agent_id,interest_key,signal_type) do update set strength=excluded.strength,signal_source=excluded.signal_source,
    consent_version=excluded.consent_version,consent_granted_at=excluded.consent_granted_at,
    updated_at=now()
  returning s.* into v_signal;

  insert into public.user_interest_graph_signal_events(
    user_id,agent_id,interest_key,signal_type,action,signal_source,consent_version
  ) values (
    p_actor_user_id,p_agent_id,v_interest_key,p_signal_type,'set',p_signal_source,p_consent_version
  );
  return query select v_signal.user_id,v_signal.agent_id,v_signal.interest_key,v_signal.signal_type,
    v_signal.strength,v_signal.signal_source,v_signal.consent_version,v_signal.consent_granted_at,
    v_signal.created_at,v_signal.updated_at;
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
declare v_signal public.user_interest_graph_signals%rowtype;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null or p_signal_type is null or p_signal_type not in ('passion','habit') then
    raise exception 'interest_signal_delete_invalid' using errcode='22023';
  end if;
  delete from public.user_interest_graph_signals s
   where s.user_id=p_actor_user_id and s.interest_key=p_interest_key
     and s.signal_type=p_signal_type and s.agent_id is not distinct from p_agent_id
  returning s.* into v_signal;
  if not found then return; end if;
  insert into public.user_interest_graph_signal_events(
    user_id,agent_id,interest_key,signal_type,action,signal_source,consent_version
  ) values (
    v_signal.user_id,v_signal.agent_id,v_signal.interest_key,v_signal.signal_type,'delete',
    v_signal.signal_source,v_signal.consent_version
  );
  return query select v_signal.interest_key,v_signal.signal_type,v_signal.agent_id;
end;
$delete_interest_signal$;

create or replace function public.clear_user_interest_graph_signals_for_actor(p_actor_user_id uuid)
returns integer
language plpgsql
security definer
set search_path = ''
as $clear_interest_signals$
declare v_deleted integer;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null then raise exception 'interest_actor_required' using errcode='22023'; end if;
  with deleted as (
    delete from public.user_interest_graph_signals s where s.user_id=p_actor_user_id
    returning s.user_id,s.agent_id,s.interest_key,s.signal_type,s.signal_source,s.consent_version
  )
  insert into public.user_interest_graph_signal_events(
    user_id,agent_id,interest_key,signal_type,action,signal_source,consent_version
  )
  select user_id,agent_id,interest_key,signal_type,'reset',signal_source,consent_version from deleted;
  get diagnostics v_deleted = row_count;
  return v_deleted;
end;
$clear_interest_signals$;

create or replace function private.refresh_interest_index_from_user_settings()
returns trigger
language plpgsql
security definer
set search_path = ''
as $refresh_settings_trigger$
begin
  if not coalesce(new.privacy_settings,'{}'::jsonb) @> '{"allow_interest_matching":true}'::jsonb then
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
  perform private.refresh_user_interest_discovery_index(new.user_id);
  return new;
end;
$refresh_settings_trigger$;

revoke all on function public.set_user_interest_graph_signal_for_actor(uuid,text,text,numeric,text,text,uuid) from public,anon,authenticated;
revoke all on function public.delete_user_interest_graph_signal_for_actor(uuid,text,text,uuid) from public,anon,authenticated;
revoke all on function public.clear_user_interest_graph_signals_for_actor(uuid) from public,anon,authenticated;
grant execute on function public.set_user_interest_graph_signal_for_actor(uuid,text,text,numeric,text,text,uuid) to service_role;
grant execute on function public.delete_user_interest_graph_signal_for_actor(uuid,text,text,uuid) to service_role;
grant execute on function public.clear_user_interest_graph_signals_for_actor(uuid) to service_role;
