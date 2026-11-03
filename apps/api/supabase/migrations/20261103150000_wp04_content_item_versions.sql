-- WP-04: durable, owner-scoped snapshots of prior content versions.
-- Additive only: does not rewrite existing content or media objects.

create table if not exists public.content_item_versions (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null,
  owner_id uuid not null,
  version integer not null check (version > 0),
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
  created_at timestamptz not null default now(),
  constraint content_item_versions_content_owner_fk
    foreign key (content_id, owner_id)
    references public.content_items(id, owner_id) on delete cascade,
  constraint content_item_versions_unique unique (content_id, version)
);

create index if not exists content_item_versions_owner_content_idx
  on public.content_item_versions(owner_id, content_id, version desc);

alter table public.content_item_versions enable row level security;
revoke all on public.content_item_versions from anon, public, authenticated;
grant select on public.content_item_versions to authenticated;
drop policy if exists content_item_versions_owner_select on public.content_item_versions;
create policy content_item_versions_owner_select
  on public.content_item_versions for select to authenticated
  using (owner_id = (select auth.uid()));

create or replace function public.content_items_capture_version()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  if new.version > old.version then
    insert into public.content_item_versions
      (content_id, owner_id, version, snapshot)
    values (
      old.id,
      old.owner_id,
      old.version,
      jsonb_build_object(
        'content_type', old.content_type,
        'body', old.body,
        'visibility', old.visibility,
        'status', old.status,
        'moderation_status', old.moderation_status,
        'provenance', old.provenance,
        'error_code', old.error_code,
        'published_at', old.published_at,
        'updated_at', old.updated_at
      )
    )
    on conflict (content_id, version) do nothing;
  end if;
  return new;
end;
$$;

revoke all on function public.content_items_capture_version() from public, anon, authenticated;
drop trigger if exists content_items_capture_version on public.content_items;
create trigger content_items_capture_version
before update on public.content_items
for each row execute function public.content_items_capture_version();
