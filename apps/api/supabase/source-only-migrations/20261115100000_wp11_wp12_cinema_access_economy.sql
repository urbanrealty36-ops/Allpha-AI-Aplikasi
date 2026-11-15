-- SOURCE ONLY — WP-11/WP-12 AI Cinema lifecycle, access, telemetry and creator-economy foundation.
-- Depends on the source-only ENG-P30 Stripe subscription schema and the applied ENG-P13
-- cinema_titles/cinema_episodes + content_media schema. Do not apply to canonical production
-- or staging as part of this source implementation. No products, prices, access policies,
-- qualified-watch thresholds, royalty splits or payout rules are seeded.
begin;

-- FastAPI is the only business-write boundary for Cinema. Preserve RLS-backed public/owner
-- reads, but revoke direct client-side business DML.
revoke insert, update, delete, truncate, references, trigger
  on table public.cinema_titles, public.cinema_episodes from anon, authenticated;
grant select on table public.cinema_titles, public.cinema_episodes to anon, authenticated;
grant select, insert, update, delete
  on table public.cinema_titles, public.cinema_episodes to service_role;

-- Enforce that an episode's owner is the same owner as its parent title.
create unique index if not exists cinema_titles_id_owner_uq
  on public.cinema_titles(id, owner_id);
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'cinema_episodes_title_owner_fk'
      and conrelid = 'public.cinema_episodes'::regclass
  ) then
    alter table public.cinema_episodes
      add constraint cinema_episodes_title_owner_fk
      foreign key (title_id, owner_id)
      references public.cinema_titles(id, owner_id)
      on delete cascade;
  end if;
end
$$;

alter table public.cinema_episodes
  add column if not exists version integer not null default 1;
alter table public.cinema_titles
  add column if not exists entitlement_key text;

create table if not exists public.cinema_film_versions (
  id uuid primary key default gen_random_uuid(),
  title_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  version integer not null check (version > 0),
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique(title_id, version),
  foreign key (title_id, owner_id)
    references public.cinema_titles(id, owner_id) on delete cascade
);
create index if not exists cinema_film_versions_owner_created_idx
  on public.cinema_film_versions(owner_id, created_at desc);

create table if not exists public.cinema_creator_credits (
  id uuid primary key default gen_random_uuid(),
  title_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  contributor_type text not null check (contributor_type in ('human','agent')),
  contributor_user_id uuid references auth.users(id) on delete restrict,
  contributor_agent_id uuid references public.ai_agents(id) on delete restrict,
  role text not null check (char_length(btrim(role)) between 2 and 80),
  attribution_label text not null check (char_length(btrim(attribution_label)) between 1 and 160),
  disclosure text not null default 'AI-assisted contribution',
  provenance jsonb not null default '{}'::jsonb check (jsonb_typeof(provenance) = 'object'),
  created_at timestamptz not null default now(),
  foreign key (title_id, owner_id)
    references public.cinema_titles(id, owner_id) on delete cascade,
  check (
    (contributor_type = 'human' and contributor_user_id is not null and contributor_agent_id is null)
    or
    (contributor_type = 'agent' and contributor_agent_id is not null and contributor_user_id is null)
  )
);
create index if not exists cinema_creator_credits_title_idx
  on public.cinema_creator_credits(title_id, created_at);

-- Plan rows are operator-managed and remain empty until Finance/Product approval.
create table if not exists public.cinema_collaborators (
  id uuid primary key default gen_random_uuid(),
  title_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  collaborator_user_id uuid references auth.users(id) on delete restrict,
  collaborator_agent_id uuid references public.ai_agents(id) on delete restrict,
  role text not null check (char_length(btrim(role)) between 2 and 80),
  permissions text[] not null default '{}'::text[] check (
    permissions <@ array['edit_metadata','upload_episodes','manage_credits','submit_review']::text[]
  ),
  status text not null default 'invited' check (status in ('invited','active','revoked','expired')),
  invited_by uuid not null references auth.users(id) on delete restrict,
  accepted_by uuid references auth.users(id) on delete set null,
  accepted_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (title_id,owner_id) references public.cinema_titles(id,owner_id) on delete cascade,
  check ((collaborator_user_id is not null and collaborator_agent_id is null)
      or (collaborator_user_id is null and collaborator_agent_id is not null)),
  check (collaborator_user_id is null or collaborator_user_id <> owner_id),
  check (expires_at is null or expires_at > created_at),
  check (status <> 'active' or accepted_at is not null)
);
create unique index if not exists cinema_collaborators_title_user_active_uq
  on public.cinema_collaborators(title_id,collaborator_user_id)
  where collaborator_user_id is not null and status in ('invited','active');
create unique index if not exists cinema_collaborators_title_agent_active_uq
  on public.cinema_collaborators(title_id,collaborator_agent_id)
  where collaborator_agent_id is not null and status in ('invited','active');
create index if not exists cinema_collaborators_owner_status_idx
  on public.cinema_collaborators(owner_id,status,created_at desc);
alter table public.cinema_collaborators enable row level security;
revoke all on public.cinema_collaborators from public,anon,authenticated,service_role;
grant select,insert,update,delete on public.cinema_collaborators to service_role;

create table if not exists public.cinema_subscription_plans (
  id uuid primary key default gen_random_uuid(),
  plan_key text not null unique check (plan_key ~ '^[a-z0-9][a-z0-9._-]{1,79}$'),
  product_key text not null unique references public.billing_products(product_key) on delete restrict,
  entitlement_key text not null check (char_length(entitlement_key) between 3 and 120),
  entitlement_version text not null check (char_length(entitlement_version) between 1 and 80),
  approval_reference text,
  configuration jsonb not null default '{}'::jsonb check (jsonb_typeof(configuration) = 'object'),
  status text not null default 'draft' check (status in ('draft','active','retired')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (status <> 'active' or (approval_reference is not null and char_length(approval_reference) >= 3))
);

create table if not exists public.cinema_subscriptions (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  billing_subscription_id uuid not null unique references public.billing_subscriptions(id) on delete restrict,
  plan_key text not null references public.cinema_subscription_plans(plan_key) on delete restrict,
  entitlement_version text not null,
  status text not null check (status in ('active','suspended','cancelled','expired','revoked')),
  valid_from timestamptz not null,
  valid_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (valid_until is null or valid_until > valid_from)
);
create index if not exists cinema_subscriptions_owner_status_idx
  on public.cinema_subscriptions(owner_user_id, status, valid_until);

-- A policy version must be explicitly approved before any viewer receives a playback URL.
create table if not exists public.cinema_access_policy_versions (
  policy_version text primary key check (char_length(policy_version) between 1 and 80),
  approval_reference text not null check (char_length(approval_reference) between 3 and 160),
  configuration jsonb not null check (jsonb_typeof(configuration) = 'object'),
  status text not null default 'draft' check (status in ('draft','approved','retired')),
  effective_at timestamptz not null,
  expires_at timestamptz,
  approved_by uuid references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  check (expires_at is null or expires_at > effective_at),
  check (status <> 'approved' or approved_by is not null)
);
create index if not exists cinema_access_policy_effective_idx
  on public.cinema_access_policy_versions(status, effective_at desc, expires_at);

create table if not exists public.cinema_playback_sessions (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  title_id uuid not null references public.cinema_titles(id) on delete restrict,
  episode_id uuid not null references public.cinema_episodes(id) on delete restrict,
  media_id uuid not null references public.content_media(id) on delete restrict,
  entitlement_id uuid references public.playback_entitlements(id) on delete restrict,
  access_policy_version text not null references public.cinema_access_policy_versions(policy_version) on delete restrict,
  session_token_hash text not null check (session_token_hash ~ '^[0-9a-f]{64}$'),
  status text not null default 'active' check (status in ('active','finished','expired','revoked')),
  duration_seconds integer check (duration_seconds is null or duration_seconds > 0),
  last_position_seconds integer not null default 0 check (last_position_seconds >= 0),
  watched_seconds integer not null default 0 check (watched_seconds >= 0),
  started_at timestamptz not null default now(),
  last_heartbeat_at timestamptz not null default now(),
  expires_at timestamptz not null,
  finished_at timestamptz,
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_user_id, idempotency_key),
  check (expires_at > started_at),
  check (duration_seconds is null or last_position_seconds <= duration_seconds)
);
create index if not exists cinema_playback_sessions_owner_active_idx
  on public.cinema_playback_sessions(owner_user_id, status, expires_at);
create index if not exists cinema_playback_sessions_title_started_idx
  on public.cinema_playback_sessions(title_id, started_at desc);

create table if not exists public.cinema_playback_events (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.cinema_playback_sessions(id) on delete restrict,
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  event_id uuid not null unique,
  event_type text not null check (event_type in ('heartbeat','finish')),
  position_seconds integer not null check (position_seconds >= 0),
  observed_seconds integer not null default 0 check (observed_seconds between 0 and 30),
  created_at timestamptz not null default now()
);
create index if not exists cinema_playback_events_session_created_idx
  on public.cinema_playback_events(session_id, created_at);

create table if not exists public.cinema_watch_policy_versions (
  policy_version text primary key check (char_length(policy_version) between 1 and 80),
  approval_reference text not null check (char_length(approval_reference) between 3 and 160),
  configuration jsonb not null check (jsonb_typeof(configuration) = 'object'),
  status text not null default 'draft' check (status in ('draft','approved','retired')),
  effective_at timestamptz not null,
  expires_at timestamptz,
  approved_by uuid references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  check (expires_at is null or expires_at > effective_at),
  check (status <> 'approved' or approved_by is not null)
);
create table if not exists public.cinema_qualified_watches (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null unique references public.cinema_playback_sessions(id) on delete restrict,
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  title_id uuid not null references public.cinema_titles(id) on delete restrict,
  episode_id uuid not null references public.cinema_episodes(id) on delete restrict,
  policy_version text references public.cinema_watch_policy_versions(policy_version) on delete restrict,
  status text not null default 'pending_policy' check (status in ('pending_policy','qualified','rejected','reversed')),
  qualified_seconds integer not null default 0 check (qualified_seconds >= 0),
  decision_reason text,
  evaluated_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists cinema_qualified_watches_owner_created_idx
  on public.cinema_qualified_watches(owner_user_id, created_at desc);
create index if not exists cinema_qualified_watches_status_idx
  on public.cinema_qualified_watches(status, created_at);

create table if not exists public.cinema_creator_earning_policy_versions (
  policy_version text primary key check (char_length(policy_version) between 1 and 80),
  approval_reference text not null check (char_length(approval_reference) between 3 and 160),
  configuration jsonb not null check (jsonb_typeof(configuration) = 'object'),
  status text not null default 'draft' check (status in ('draft','approved','retired')),
  effective_at timestamptz not null,
  expires_at timestamptz,
  approved_by uuid references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  check (expires_at is null or expires_at > effective_at),
  check (status <> 'approved' or approved_by is not null)
);
create table if not exists public.cinema_creator_earnings (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  title_id uuid not null references public.cinema_titles(id) on delete restrict,
  qualified_watch_id uuid not null references public.cinema_qualified_watches(id) on delete restrict,
  creator_credit_id uuid references public.cinema_creator_credits(id) on delete restrict,
  creator_type text not null check (creator_type in ('human','agent')),
  creator_user_id uuid references auth.users(id) on delete restrict,
  creator_agent_id uuid references public.ai_agents(id) on delete restrict,
  policy_version text references public.cinema_creator_earning_policy_versions(policy_version) on delete restrict,
  earning_credits bigint check (earning_credits is null or earning_credits >= 0),
  status text not null default 'pending_policy' check (status in ('pending_policy','approved','settled','reversed')),
  source_event_id text not null unique,
  created_at timestamptz not null default now(),
  settled_at timestamptz,
  check (
    (creator_type = 'human' and creator_user_id is not null and creator_agent_id is null)
    or
    (creator_type = 'agent' and creator_agent_id is not null and creator_user_id is null)
  ),
  check (status not in ('approved','settled') or (policy_version is not null and earning_credits is not null))
);
create index if not exists cinema_creator_earnings_owner_created_idx
  on public.cinema_creator_earnings(owner_user_id, created_at desc);
create index if not exists cinema_creator_earnings_status_idx
  on public.cinema_creator_earnings(status, created_at);

create or replace function public.sync_cinema_subscription_from_billing()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_plan public.cinema_subscription_plans%rowtype;
  v_status text;
  v_start timestamptz;
begin
  select * into v_plan
  from public.cinema_subscription_plans
  where plan_key = new.plan_key
    and entitlement_version = new.entitlement_version
    and status = 'active'
  limit 1;

  v_start := coalesce(new.current_period_start, now());
  if new.status = 'active' and found
     and (new.current_period_end is null or new.current_period_end > v_start) then
    insert into public.cinema_subscriptions
      (owner_user_id,billing_subscription_id,plan_key,entitlement_version,status,valid_from,valid_until)
    values
      (new.owner_user_id,new.id,v_plan.plan_key,new.entitlement_version,'active',v_start,new.current_period_end)
    on conflict (billing_subscription_id) do update set
      owner_user_id = excluded.owner_user_id, plan_key = excluded.plan_key,
      entitlement_version = excluded.entitlement_version, status = 'active',
      valid_from = excluded.valid_from, valid_until = excluded.valid_until, updated_at = now();

    insert into public.playback_entitlements
      (owner_user_id,entitlement_key,entitlement_version,source_subscription_id,status,valid_from,valid_until)
    values
      (new.owner_user_id,v_plan.entitlement_key,new.entitlement_version,new.id,'active',v_start,new.current_period_end)
    on conflict (owner_user_id,entitlement_key,source_subscription_id) do update set
      entitlement_version = excluded.entitlement_version, status = 'active',
      valid_from = excluded.valid_from, valid_until = excluded.valid_until, updated_at = now();
  else
    v_status := case when new.status in ('canceled','incomplete_expired') then 'cancelled' else 'suspended' end;
    update public.cinema_subscriptions set status = v_status, updated_at = now()
      where billing_subscription_id = new.id;
    update public.playback_entitlements set status = 'suspended', updated_at = now()
      where source_subscription_id = new.id;
  end if;
  return new;
end;
$$;
drop trigger if exists billing_subscription_cinema_sync on public.billing_subscriptions;
create trigger billing_subscription_cinema_sync
  after insert or update of status, plan_key, entitlement_version, current_period_start, current_period_end
  on public.billing_subscriptions
  for each row execute function public.sync_cinema_subscription_from_billing();

create or replace function public.cinema_record_playback_heartbeat(
  p_session_id uuid, p_owner_user_id uuid, p_session_token_hash text,
  p_event_id uuid, p_position_seconds integer
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_session public.cinema_playback_sessions%rowtype;
  v_elapsed integer;
  v_position_delta integer;
  v_observed integer;
  v_existing public.cinema_playback_events%rowtype;
begin
  select * into v_existing from public.cinema_playback_events where event_id = p_event_id;
  if found then
    if v_existing.owner_user_id <> p_owner_user_id or v_existing.session_id <> p_session_id then
      raise exception 'CINEMA_PLAYBACK_EVENT_CONFLICT' using errcode = '23505';
    end if;
    select * into v_session from public.cinema_playback_sessions where id = p_session_id;
    return jsonb_build_object('outcome','replayed','watched_seconds',coalesce(v_session.watched_seconds,0));
  end if;

  select * into v_session from public.cinema_playback_sessions
  where id = p_session_id and owner_user_id = p_owner_user_id
    and session_token_hash = p_session_token_hash
  for update;
  if not found or v_session.status <> 'active' or v_session.expires_at <= now() then
    raise exception 'CINEMA_PLAYBACK_SESSION_NOT_ACTIVE' using errcode = '42501';
  end if;
  if p_position_seconds < 0
     or (v_session.duration_seconds is not null and p_position_seconds > v_session.duration_seconds) then
    raise exception 'CINEMA_PLAYBACK_POSITION_INVALID' using errcode = '22023';
  end if;

  v_elapsed := greatest(0, least(30, floor(extract(epoch from (now() - v_session.last_heartbeat_at)))::integer));
  v_position_delta := greatest(0, p_position_seconds - v_session.last_position_seconds);
  v_observed := least(v_elapsed, v_position_delta);

  insert into public.cinema_playback_events
    (session_id,owner_user_id,event_id,event_type,position_seconds,observed_seconds)
  values (p_session_id,p_owner_user_id,p_event_id,'heartbeat',p_position_seconds,v_observed);

  update public.cinema_playback_sessions
  set last_position_seconds = greatest(last_position_seconds,p_position_seconds),
      watched_seconds = watched_seconds + v_observed,
      last_heartbeat_at = now(), updated_at = now()
  where id = p_session_id returning * into v_session;

  return jsonb_build_object('outcome','recorded','observed_seconds',v_observed,
                            'watched_seconds',v_session.watched_seconds);
end;
$$;

create or replace function public.cinema_finish_playback_session(
  p_session_id uuid, p_owner_user_id uuid, p_session_token_hash text,
  p_event_id uuid, p_position_seconds integer
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_session public.cinema_playback_sessions%rowtype;
begin
  select * into v_session from public.cinema_playback_sessions
  where id = p_session_id and owner_user_id = p_owner_user_id
    and session_token_hash = p_session_token_hash
  for update;
  if not found then raise exception 'CINEMA_PLAYBACK_SESSION_NOT_FOUND' using errcode = 'P0002'; end if;
  if v_session.status = 'finished' then
    return jsonb_build_object('outcome','replayed','session_id',p_session_id);
  end if;
  if v_session.status <> 'active' or v_session.expires_at <= now() then
    raise exception 'CINEMA_PLAYBACK_SESSION_NOT_ACTIVE' using errcode = '42501';
  end if;
  if p_position_seconds < 0 or (v_session.duration_seconds is not null and p_position_seconds > v_session.duration_seconds) then
    raise exception 'CINEMA_PLAYBACK_POSITION_INVALID' using errcode = '22023';
  end if;
  insert into public.cinema_playback_events
    (session_id,owner_user_id,event_id,event_type,position_seconds,observed_seconds)
  values (p_session_id,p_owner_user_id,p_event_id,'finish',p_position_seconds,0)
  on conflict (event_id) do nothing;
  update public.cinema_playback_sessions
  set status = 'finished', finished_at = now(),
      last_position_seconds = greatest(last_position_seconds,p_position_seconds),
      last_heartbeat_at = now(), updated_at = now()
  where id = p_session_id returning * into v_session;
  insert into public.cinema_qualified_watches
    (session_id,owner_user_id,title_id,episode_id,status,qualified_seconds)
  values
    (v_session.id,v_session.owner_user_id,v_session.title_id,v_session.episode_id,
     'pending_policy',v_session.watched_seconds)
  on conflict (session_id) do nothing;
  return jsonb_build_object('outcome','finished','session_id',p_session_id,
                            'qualified_watch','pending_policy');
end;
$$;

alter table public.cinema_film_versions enable row level security;
alter table public.cinema_creator_credits enable row level security;
alter table public.cinema_subscription_plans enable row level security;
alter table public.cinema_subscriptions enable row level security;
alter table public.cinema_access_policy_versions enable row level security;
alter table public.cinema_playback_sessions enable row level security;
alter table public.cinema_playback_events enable row level security;
alter table public.cinema_watch_policy_versions enable row level security;
alter table public.cinema_qualified_watches enable row level security;
alter table public.cinema_creator_earning_policy_versions enable row level security;
alter table public.cinema_creator_earnings enable row level security;

revoke all on public.cinema_film_versions, public.cinema_creator_credits,
  public.cinema_subscription_plans, public.cinema_subscriptions,
  public.cinema_access_policy_versions, public.cinema_playback_sessions,
  public.cinema_playback_events, public.cinema_watch_policy_versions,
  public.cinema_qualified_watches, public.cinema_creator_earning_policy_versions,
  public.cinema_creator_earnings from public, anon, authenticated;
grant select, insert, update, delete on public.cinema_film_versions,
  public.cinema_creator_credits, public.cinema_subscription_plans,
  public.cinema_subscriptions, public.cinema_access_policy_versions,
  public.cinema_playback_sessions, public.cinema_playback_events,
  public.cinema_watch_policy_versions, public.cinema_qualified_watches,
  public.cinema_creator_earning_policy_versions, public.cinema_creator_earnings
  to service_role;

revoke all on function public.sync_cinema_subscription_from_billing() from public, anon, authenticated;
revoke all on function public.cinema_record_playback_heartbeat(uuid,uuid,text,uuid,integer) from public, anon, authenticated;
revoke all on function public.cinema_finish_playback_session(uuid,uuid,text,uuid,integer) from public, anon, authenticated;
grant execute on function public.cinema_record_playback_heartbeat(uuid,uuid,text,uuid,integer) to service_role;
grant execute on function public.cinema_finish_playback_session(uuid,uuid,text,uuid,integer) to service_role;

comment on table public.cinema_playback_sessions is 'Owner-scoped server-issued playback sessions. Client telemetry is raw evidence; qualification requires an approved versioned policy.';
comment on table public.cinema_qualified_watches is 'Qualified Watch decisions remain pending until an approved cinema_watch_policy_versions record and evaluator are configured.';
comment on table public.cinema_creator_earnings is 'Non-cash creator earning ledger. No creator/platform split, cash payout or withdrawal is enabled by default.';

commit;
