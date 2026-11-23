begin;

-- ENG-P13 continuation: bind the existing durable generation queue to canonical
-- Cinema titles and persist immutable artifact metadata. No replacement queue,
-- wallet, storage bucket, or duplicate film catalogue is introduced.

create table if not exists public.cinema_generation_job_links (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  cinema_title_id uuid not null references public.cinema_titles(id) on delete cascade,
  generation_job_id uuid not null references public.generation_jobs(id) on delete restrict,
  purpose text not null default 'film_generation'
    check (purpose in ('film_generation','trailer_generation','episode_generation','scene_generation','poster_generation')),
  scene_key text,
  created_at timestamptz not null default now(),
  unique (generation_job_id),
  unique (cinema_title_id, purpose, scene_key)
);

create index if not exists cinema_generation_job_links_title_idx
  on public.cinema_generation_job_links(owner_user_id, cinema_title_id, created_at desc);

create table if not exists public.generation_artifacts (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  generation_job_id uuid not null references public.generation_jobs(id) on delete restrict,
  cinema_title_id uuid references public.cinema_titles(id) on delete set null,
  cinema_episode_id uuid references public.cinema_episodes(id) on delete set null,
  artifact_kind text not null
    check (artifact_kind in ('screenplay','scene','render','poster','trailer','subtitle','thumbnail','other')),
  storage_bucket text not null check (char_length(storage_bucket) between 1 and 100),
  storage_path text not null check (char_length(storage_path) between 1 and 1024),
  content_type text not null check (char_length(content_type) between 1 and 160),
  byte_size bigint not null check (byte_size >= 0),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now(),
  unique (storage_bucket, storage_path),
  unique (generation_job_id, artifact_kind, sha256)
);

create index if not exists generation_artifacts_owner_created_idx
  on public.generation_artifacts(owner_user_id, created_at desc);
create index if not exists generation_artifacts_job_idx
  on public.generation_artifacts(generation_job_id, created_at);

alter table public.cinema_generation_job_links enable row level security;
alter table public.generation_artifacts enable row level security;
revoke all on public.cinema_generation_job_links, public.generation_artifacts from public, anon, authenticated;
grant select, insert, update, delete on public.cinema_generation_job_links, public.generation_artifacts to service_role;

-- The service role owns writes; this readiness RPC reports only structural
-- readiness and deliberately does not expose row data or credentials.
create or replace function public.cinema_generation_schema_readiness()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'ready',
      to_regclass('public.cinema_titles') is not null
      and to_regclass('public.cinema_episodes') is not null
      and to_regclass('public.generation_jobs') is not null
      and to_regclass('public.cinema_generation_job_links') is not null
      and to_regclass('public.generation_artifacts') is not null,
    'components', jsonb_build_object(
      'cinema_titles', to_regclass('public.cinema_titles') is not null,
      'cinema_episodes', to_regclass('public.cinema_episodes') is not null,
      'generation_jobs', to_regclass('public.generation_jobs') is not null,
      'cinema_generation_job_links', to_regclass('public.cinema_generation_job_links') is not null,
      'generation_artifacts', to_regclass('public.generation_artifacts') is not null
    )
  );
$$;
revoke all on function public.cinema_generation_schema_readiness() from public, anon, authenticated;
grant execute on function public.cinema_generation_schema_readiness() to service_role;

commit;