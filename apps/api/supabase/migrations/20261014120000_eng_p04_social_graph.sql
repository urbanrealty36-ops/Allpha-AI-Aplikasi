-- ENG-P04 Social Graph: user-scoped follows, blocks, mutes and interest preferences.
-- This migration is version-controlled only. Do not apply to production as part of this code change.

create table if not exists public.social_edges (
  id uuid primary key default gen_random_uuid(),
  actor_user_id uuid not null references auth.users(id) on delete cascade,
  target_user_id uuid not null references auth.users(id) on delete cascade,
  edge_type text not null check (edge_type in ('follow','block','mute')),
  status text not null default 'active' check (status in ('requested','active')),
  created_at timestamptz not null default now(),
  constraint social_edges_no_self check (actor_user_id <> target_user_id),
  constraint social_edges_unique unique (actor_user_id, target_user_id, edge_type),
  constraint social_edges_follow_status check (edge_type = 'follow' or status = 'active')
);
create index if not exists social_edges_actor_type_created_idx
  on public.social_edges(actor_user_id, edge_type, created_at desc);
create index if not exists social_edges_target_type_created_idx
  on public.social_edges(target_user_id, edge_type, created_at desc);

create table if not exists public.user_interests (
  user_id uuid not null references auth.users(id) on delete cascade,
  interest_key text not null check (interest_key ~ '^[a-z0-9][a-z0-9._-]{0,79}$'),
  preference text not null default 'interested' check (preference in ('interested','not_interested')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, interest_key)
);
create index if not exists user_interests_key_idx on public.user_interests(interest_key);

create or replace function public.enforce_social_edge_policy()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare target_visibility text;
begin
  if new.actor_user_id = new.target_user_id then
    raise exception using errcode = '23514', message = 'social edge cannot target self';
  end if;

  if new.edge_type = 'follow' then
    if exists (
      select 1 from public.social_edges e
      where e.edge_type = 'block'
        and ((e.actor_user_id = new.actor_user_id and e.target_user_id = new.target_user_id)
          or (e.actor_user_id = new.target_user_id and e.target_user_id = new.actor_user_id))
    ) then
      raise exception using errcode = '42501', message = 'follow disallowed by block';
    end if;
    -- An explicit accept action may change requested -> active. Do not reset that decision.
    if tg_op = 'UPDATE' and old.status = 'requested' and new.status = 'active' then
      return new;
    end if;
    select p.visibility into target_visibility
      from public.profiles p where p.id = new.target_user_id;
    if target_visibility = 'private' then
      new.status := 'requested';
    else
      new.status := 'active';
    end if;
  elsif new.edge_type = 'block' then
    new.status := 'active';
    delete from public.social_edges e
      where e.edge_type = 'follow'
        and ((e.actor_user_id = new.actor_user_id and e.target_user_id = new.target_user_id)
          or (e.actor_user_id = new.target_user_id and e.target_user_id = new.actor_user_id));
  else
    new.status := 'active';
  end if;
  return new;
end;
$$;
revoke all on function public.enforce_social_edge_policy() from public, anon, authenticated;
drop trigger if exists social_edges_policy_before_write on public.social_edges;
create trigger social_edges_policy_before_write
before insert or update of edge_type, actor_user_id, target_user_id, status
on public.social_edges
for each row execute function public.enforce_social_edge_policy();

alter table public.social_edges enable row level security;
alter table public.user_interests enable row level security;

drop policy if exists social_edges_select_participant on public.social_edges;
create policy social_edges_select_participant on public.social_edges
for select to authenticated
using (
  actor_user_id = (select auth.uid())
  or (edge_type = 'block' and target_user_id = (select auth.uid()))
  or (edge_type = 'follow' and status = 'requested' and target_user_id = (select auth.uid()))
);
drop policy if exists social_edges_insert_actor on public.social_edges;
create policy social_edges_insert_actor on public.social_edges
for insert to authenticated
with check (actor_user_id = (select auth.uid()) and target_user_id <> (select auth.uid()));
drop policy if exists social_edges_update_follow_request on public.social_edges;
create policy social_edges_update_follow_request on public.social_edges
for update to authenticated
using (edge_type = 'follow' and status = 'requested' and target_user_id = (select auth.uid()))
with check (edge_type = 'follow' and status = 'active' and target_user_id = (select auth.uid()));

drop policy if exists social_edges_delete_actor on public.social_edges;
create policy social_edges_delete_actor on public.social_edges
for delete to authenticated
using (
  actor_user_id = (select auth.uid())
  or (edge_type = 'follow' and status = 'requested' and target_user_id = (select auth.uid()))
);

drop policy if exists user_interests_select_self on public.user_interests;
create policy user_interests_select_self on public.user_interests
for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists user_interests_insert_self on public.user_interests;
create policy user_interests_insert_self on public.user_interests
for insert to authenticated with check (user_id = (select auth.uid()));
drop policy if exists user_interests_update_self on public.user_interests;
create policy user_interests_update_self on public.user_interests
for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
drop policy if exists user_interests_delete_self on public.user_interests;
create policy user_interests_delete_self on public.user_interests
for delete to authenticated using (user_id = (select auth.uid()));

grant select, insert, update, delete on public.social_edges to authenticated;
drop trigger if exists user_interests_set_updated_at on public.user_interests;
create trigger user_interests_set_updated_at before update on public.user_interests
for each row execute function public.set_updated_at();

grant select, insert, update, delete on public.user_interests to authenticated;
