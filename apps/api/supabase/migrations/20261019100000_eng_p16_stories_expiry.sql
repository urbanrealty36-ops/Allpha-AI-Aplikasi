-- ENG-P16: temporary Stories/Moments lifecycle on canonical content_items.
-- Additive only: stories reuse content_items/content_media; public reads must filter expires_at server-side.
alter table public.content_items
  add column if not exists expires_at timestamptz;

create index if not exists content_stories_active_expiry_idx
  on public.content_items (expires_at asc, published_at desc)
  where content_type = 'story' and status = 'published' and moderation_status = 'approved';

create index if not exists content_stories_owner_idx
  on public.content_items (owner_id, created_at desc)
  where content_type = 'story';

create or replace function public.content_items_story_expiry()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
declare
  ttl_hours integer;
begin
  if new.content_type <> 'story' then
    new.expires_at := null;
    return new;
  end if;

  if new.status = 'published' and new.moderation_status = 'approved' then
    ttl_hours := coalesce(
      nullif(new.provenance #>> '{stories,expires_after_hours}', '')::integer,
      24
    );
    if ttl_hours < 1 or ttl_hours > 168 then
      raise exception 'story expiry must be between 1 and 168 hours'
        using errcode = '23514';
    end if;
    if new.published_at is null then
      new.published_at := now();
    end if;
    if tg_op = 'INSERT' or old.status <> 'published' or old.moderation_status <> 'approved' or new.expires_at is null then
      new.expires_at := new.published_at + make_interval(hours => ttl_hours);
    end if;
  elsif new.status <> 'published' or new.moderation_status <> 'approved' then
    new.expires_at := null;
  end if;
  return new;
end;
$$;

revoke all on function public.content_items_story_expiry() from public, anon, authenticated;
drop trigger if exists content_items_story_expiry on public.content_items;
create trigger content_items_story_expiry
  before insert or update of content_type, status, moderation_status, published_at, provenance, expires_at
  on public.content_items
  for each row execute function public.content_items_story_expiry();

alter table public.content_items
  drop constraint if exists content_story_published_requires_expiry;
alter table public.content_items
  add constraint content_story_published_requires_expiry
  check (content_type <> 'story' or status <> 'published' or (moderation_status = 'approved' and expires_at is not null));

comment on column public.content_items.expires_at is
  'Server-enforced lifecycle expiry for temporary content such as Stories; null for non-expiring content and non-published Stories.';
