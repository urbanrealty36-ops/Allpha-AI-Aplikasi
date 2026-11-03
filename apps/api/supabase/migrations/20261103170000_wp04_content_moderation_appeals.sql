-- WP-04 moderation appeal lifecycle. Apply through the approved migration path.
create table if not exists public.content_appeals (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_items(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  submitted_version integer not null check (submitted_version > 0),
  reason text not null check (char_length(reason) between 8 and 2000),
  status text not null default 'pending' check (status in ('pending','approved','rejected','withdrawn')),
  decision_reason text,
  decided_by uuid references auth.users(id) on delete set null,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint content_appeals_content_owner_fk foreign key (content_id, owner_id)
    references public.content_items(id, owner_id) on delete cascade,
  constraint content_appeals_decision_consistency check (
    (status = 'pending' and decided_by is null and decided_at is null)
    or (status <> 'pending' and (decided_by is not null or status = 'withdrawn'))
  )
);
create unique index if not exists content_appeals_one_pending_per_content
  on public.content_appeals(content_id) where status = 'pending';
create index if not exists content_appeals_owner_created_idx
  on public.content_appeals(owner_id, created_at desc);
create index if not exists content_appeals_queue_idx
  on public.content_appeals(status, created_at asc) where status = 'pending';

alter table public.content_appeals enable row level security;
revoke all on public.content_appeals from anon, public, authenticated;
grant select, insert on public.content_appeals to authenticated;
drop policy if exists content_appeals_owner_select on public.content_appeals;
create policy content_appeals_owner_select on public.content_appeals
  for select to authenticated using (owner_id = (select auth.uid()));
drop policy if exists content_appeals_owner_insert on public.content_appeals;
create policy content_appeals_owner_insert on public.content_appeals
  for insert to authenticated with check (
    owner_id = (select auth.uid())
    and status = 'pending'
    and decided_by is null
    and decided_at is null
    and exists (
      select 1 from public.content_items c
      where c.id = content_id and c.owner_id = (select auth.uid())
        and c.status = 'failed' and c.moderation_status = 'rejected'
        and c.version = submitted_version
    )
  );

create or replace function public.content_appeals_touch_updated_at()
returns trigger language plpgsql
set search_path = pg_catalog, public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
revoke all on function public.content_appeals_touch_updated_at() from public, anon, authenticated;
drop trigger if exists content_appeals_touch_updated_at on public.content_appeals;
create trigger content_appeals_touch_updated_at before update on public.content_appeals
for each row execute function public.content_appeals_touch_updated_at();
