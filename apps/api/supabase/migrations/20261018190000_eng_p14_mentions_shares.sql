-- ENG-P14 follow-up: durable mentions and share events for social interactions.
create table if not exists public.content_shares (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_items(id) on delete cascade,
  actor_user_id uuid not null references auth.users(id) on delete cascade,
  share_target text not null check (share_target in ('copy_link','native_share','external')),
  created_at timestamptz not null default now()
);
create index if not exists content_shares_content_created_idx on public.content_shares(content_id, created_at desc);
create index if not exists content_shares_actor_created_idx on public.content_shares(actor_user_id, created_at desc);

create table if not exists public.content_mentions (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_items(id) on delete cascade,
  comment_id uuid references public.content_comments(id) on delete cascade,
  mentioner_user_id uuid not null references auth.users(id) on delete cascade,
  mentioned_user_id uuid not null references auth.users(id) on delete cascade,
  source text not null check (source in ('content','comment')),
  created_at timestamptz not null default now(),
  constraint content_mentions_no_self check (mentioner_user_id <> mentioned_user_id),
  constraint content_mentions_source_comment check (
    (source='comment' and comment_id is not null) or (source='content' and comment_id is null)
  )
);
create unique index if not exists content_mentions_unique_comment_target_idx
  on public.content_mentions(comment_id, mentioned_user_id) where comment_id is not null;
create unique index if not exists content_mentions_unique_content_target_idx
  on public.content_mentions(content_id, mentioner_user_id, mentioned_user_id) where comment_id is null;
create index if not exists content_mentions_target_created_idx on public.content_mentions(mentioned_user_id, created_at desc);
create index if not exists content_mentions_content_created_idx on public.content_mentions(content_id, created_at desc);

alter table public.content_shares enable row level security;
alter table public.content_mentions enable row level security;
revoke all on public.content_shares, public.content_mentions from public, anon, authenticated;
grant all on public.content_shares, public.content_mentions to service_role;

create or replace function public.record_content_comment_mentions()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  mention_match text[];
  target_user_id uuid;
begin
  for mention_match in
    select regexp_matches(new.body, '@([a-z0-9][a-z0-9._-]{0,79})', 'g')
  loop
    target_user_id := null;
    select p.id into target_user_id
      from public.profiles p
      where lower(p.username) = lower(mention_match[1])
        and p.visibility = 'public'
        and p.account_status = 'active'
        and p.id <> new.actor_user_id
      limit 1;
    if target_user_id is not null
      and not exists (
        select 1 from public.social_edges e
        where e.edge_type = 'block'
          and ((e.actor_user_id = new.actor_user_id and e.target_user_id = target_user_id)
            or (e.actor_user_id = target_user_id and e.target_user_id = new.actor_user_id))
      )
    then
      insert into public.content_mentions(content_id, comment_id, mentioner_user_id, mentioned_user_id, source)
      values (new.content_id, new.id, new.actor_user_id, target_user_id, 'comment')
      on conflict do nothing;
    end if;
  end loop;
  return new;
end;
$$;
revoke all on function public.record_content_comment_mentions() from public, anon, authenticated;
drop trigger if exists content_comments_record_mentions on public.content_comments;
create trigger content_comments_record_mentions after insert on public.content_comments
for each row execute function public.record_content_comment_mentions();
