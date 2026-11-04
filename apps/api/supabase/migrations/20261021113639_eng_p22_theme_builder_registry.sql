-- ENG-P22 canonical Theme Builder and immutable Theme manifest versions.
-- Source migration only until the approved migration/reconciliation gate is satisfied.
-- No client receives direct access; all lifecycle writes pass through canonical FastAPI.
create table if not exists public.spatial_themes (
  theme_key text primary key check (theme_key ~ '^[a-z0-9][a-z0-9._-]{2,119}$'),
  display_name text not null check (char_length(display_name) between 2 and 160),
  description text not null default '' check (char_length(description) <= 2000),
  status text not null default 'draft' check (status in ('draft','published','deprecated','retired')),
  active_version integer,
  created_by uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((status = 'published') = (active_version is not null))
);

create table if not exists public.spatial_theme_versions (
  theme_key text not null references public.spatial_themes(theme_key) on delete restrict,
  version integer not null check (version > 0),
  schema_version text not null default '1.0' check (schema_version = '1.0'),
  manifest jsonb not null check (jsonb_typeof(manifest) = 'object'),
  manifest_sha256 text not null check (manifest_sha256 ~ '^[a-f0-9]{64}$'),
  status text not null default 'draft' check (status in ('draft','review','approved','published','deprecated','revoked')),
  created_by uuid not null,
  created_at timestamptz not null default now(),
  published_at timestamptz,
  primary key (theme_key, version),
  check ((published_at is not null) = (status in ('published','deprecated','revoked'))),
  check (manifest->>'theme_key' = theme_key),
  check (manifest->>'schema_version' = schema_version)
);

alter table public.spatial_themes
  add constraint spatial_themes_active_version_fk
  foreign key (theme_key, active_version)
  references public.spatial_theme_versions(theme_key, version)
  deferrable initially deferred;

create index if not exists spatial_themes_public_lookup
  on public.spatial_themes (theme_key, active_version)
  where status = 'published';

create index if not exists spatial_theme_versions_lifecycle
  on public.spatial_theme_versions (theme_key, status, version desc);

create or replace function public.spatial_theme_version_immutable_guard()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'spatial theme versions are immutable; create a new version instead'
      using errcode = '55000';
  end if;
  if new.theme_key is distinct from old.theme_key
     or new.version is distinct from old.version
     or new.schema_version is distinct from old.schema_version
     or new.manifest is distinct from old.manifest
     or new.manifest_sha256 is distinct from old.manifest_sha256
     or new.created_by is distinct from old.created_by
     or new.created_at is distinct from old.created_at then
    raise exception 'spatial theme version content is immutable; create a new version instead'
      using errcode = '55000';
  end if;
  if old.status in ('deprecated','revoked') and new.status is distinct from old.status then
    raise exception 'deprecated/revoked theme versions cannot be reactivated'
      using errcode = '55000';
  end if;
  if old.status = 'published' and new.status not in ('published','deprecated','revoked') then
    raise exception 'published theme versions can only be deprecated or revoked'
      using errcode = '55000';
  end if;
  return new;
end;
$$;

drop trigger if exists spatial_theme_version_immutable_guard on public.spatial_theme_versions;
create trigger spatial_theme_version_immutable_guard
before update or delete on public.spatial_theme_versions
for each row execute function public.spatial_theme_version_immutable_guard();

alter table public.spatial_themes enable row level security;
alter table public.spatial_theme_versions enable row level security;
revoke all on public.spatial_themes from anon, authenticated;
revoke all on public.spatial_theme_versions from anon, authenticated;
grant select, insert, update, delete on public.spatial_themes to service_role;
grant select, insert, update, delete on public.spatial_theme_versions to service_role;

comment on table public.spatial_themes is 'Canonical Theme identity and active published version; server-only writes through FastAPI.';
comment on table public.spatial_theme_versions is 'Immutable declarative Theme manifest versions pinned to canonical spatial asset versions.';
