-- ENG-P19 canonical community, collaboration workspace, mission and moderation data.
-- All business reads/writes are mediated by the FastAPI service-role boundary.
create table if not exists public.communities (
  id uuid primary key default gen_random_uuid(),
  name text not null check (length(trim(name)) between 2 and 80),
  slug text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$'),
  description text not null default '' check (length(description) <= 1000),
  visibility text not null default 'public' check (visibility in ('public','private')),
  status text not null default 'active' check (status in ('active','archived','suspended')),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table if not exists public.community_memberships (
  community_id uuid not null references public.communities(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner','moderator','member')),
  status text not null default 'active' check (status in ('active','removed','banned','left')),
  joined_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (community_id,user_id)
);
create unique index if not exists community_one_active_owner_idx on public.community_memberships(community_id) where role='owner' and status='active';
create index if not exists community_memberships_user_status_idx on public.community_memberships(user_id,status,community_id);
create table if not exists public.community_invites (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  created_by uuid not null references auth.users(id) on delete restrict,
  token_hash text not null unique check (length(token_hash)=64),
  role text not null default 'member' check (role in ('member','moderator')),
  expires_at timestamptz not null,
  accepted_at timestamptz,
  accepted_by uuid references auth.users(id) on delete set null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists community_invites_active_idx on public.community_invites(community_id,expires_at) where accepted_at is null and revoked_at is null;
create table if not exists public.community_posts (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  author_id uuid not null references auth.users(id) on delete restrict,
  body text not null check (length(trim(body)) between 1 and 5000),
  post_type text not null default 'discussion' check (post_type in ('discussion','announcement','resource','event')),
  status text not null default 'published' check (status in ('draft','published','hidden','removed')),
  version integer not null default 1 check (version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists community_posts_timeline_idx on public.community_posts(community_id,status,created_at desc);
create table if not exists public.community_reports (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  reporter_id uuid not null references auth.users(id) on delete restrict,
  reason text not null check (length(trim(reason)) between 8 and 500),
  status text not null default 'open' check (status in ('open','reviewing','resolved','dismissed')),
  reviewer_id uuid references auth.users(id) on delete set null,
  review_reason text,
  reviewed_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists community_reports_queue_idx on public.community_reports(status,created_at desc);
create table if not exists public.workspaces (
  id uuid primary key default gen_random_uuid(),
  title text not null check (length(trim(title)) between 2 and 120),
  description text not null default '' check (length(description) <= 1000),
  created_by uuid not null references auth.users(id) on delete restrict,
  community_id uuid references public.communities(id) on delete cascade,
  visibility text not null default 'private' check (visibility in ('private','community')),
  status text not null default 'active' check (status in ('active','archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((visibility='private') or community_id is not null)
);
create index if not exists workspaces_community_idx on public.workspaces(community_id,status,updated_at desc);
create table if not exists public.workspace_memberships (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'viewer' check (role in ('owner','editor','viewer')),
  status text not null default 'active' check (status in ('active','removed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (workspace_id,user_id)
);
create index if not exists workspace_memberships_user_idx on public.workspace_memberships(user_id,status,workspace_id);
create table if not exists public.workspace_documents (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  title text not null check (length(trim(title)) between 1 and 160),
  body text not null default '' check (length(body) <= 50000),
  version integer not null default 1 check (version > 0),
  status text not null default 'active' check (status in ('active','archived')),
  created_by uuid not null references auth.users(id) on delete restrict,
  updated_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id,workspace_id)
);
create index if not exists workspace_documents_updated_idx on public.workspace_documents(workspace_id,status,updated_at desc);
create table if not exists public.workspace_document_versions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.workspace_documents(id) on delete cascade,
  version integer not null check (version > 0),
  title text not null,
  body text not null default '',
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique (document_id,version)
);
create index if not exists workspace_document_versions_history_idx on public.workspace_document_versions(document_id,version desc);
create table if not exists public.workspace_annotations (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  document_id uuid not null,
  author_id uuid not null references auth.users(id) on delete restrict,
  body text not null check (length(trim(body)) between 1 and 4000),
  anchor jsonb not null default '{}'::jsonb check (jsonb_typeof(anchor)='object'),
  status text not null default 'active' check (status in ('active','resolved','removed')),
  created_at timestamptz not null default now(),
  foreign key (document_id,workspace_id) references public.workspace_documents(id,workspace_id) on delete cascade
);
create index if not exists workspace_annotations_doc_idx on public.workspace_annotations(workspace_id,document_id,status,created_at);
create table if not exists public.workspace_presence (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  last_seen_at timestamptz not null default now(),
  primary key (workspace_id,user_id)
);
create index if not exists workspace_presence_active_idx on public.workspace_presence(workspace_id,last_seen_at desc);
create table if not exists public.community_missions (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  created_by uuid not null references auth.users(id) on delete restrict,
  title text not null check (length(trim(title)) between 2 and 120),
  description text not null default '' check (length(description) <= 2000),
  target_count integer not null default 1 check (target_count between 1 and 100000),
  starts_at timestamptz,
  ends_at timestamptz,
  status text not null default 'active' check (status in ('draft','active','paused','completed','archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (ends_at is null or starts_at is null or ends_at > starts_at)
);
create index if not exists community_missions_active_idx on public.community_missions(community_id,status,created_at desc);
create table if not exists public.community_mission_progress (
  mission_id uuid not null references public.community_missions(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  progress_count integer not null default 0 check (progress_count >= 0),
  status text not null default 'not_started' check (status in ('not_started','in_progress','completed')),
  updated_at timestamptz not null default now(),
  primary key (mission_id,user_id)
);
create index if not exists community_mission_progress_user_idx on public.community_mission_progress(user_id,status,community_id);
-- These records contain private membership, invite tokens (hashed), collaborative content and moderation evidence.
-- Clients must use the authenticated FastAPI API, never direct table access.
do $$
declare t text;
begin
  foreach t in array array[
    'communities','community_memberships','community_invites','community_posts','community_reports',
    'workspaces','workspace_memberships','workspace_documents','workspace_document_versions',
    'workspace_annotations','workspace_presence','community_missions','community_mission_progress'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on table public.%I from anon, authenticated', t);
    execute format('grant all on table public.%I to service_role', t);
  end loop;
end $$;
