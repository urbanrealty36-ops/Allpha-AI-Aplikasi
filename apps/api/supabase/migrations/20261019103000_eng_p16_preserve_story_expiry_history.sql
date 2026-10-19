-- ENG-P16 follow-up: preserve expiry timestamps for archived/deleted Stories.
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
    if tg_op = 'INSERT' then
      new.expires_at := new.published_at + make_interval(hours => ttl_hours);
    elsif old.status <> 'published' or old.moderation_status <> 'approved' or new.expires_at is null then
      new.expires_at := new.published_at + make_interval(hours => ttl_hours);
    end if;
  elsif new.status in ('archived', 'deleted') then
    new.expires_at := coalesce(new.expires_at, now());
  else
    new.expires_at := null;
  end if;
  return new;
end;
$$;
revoke all on function public.content_items_story_expiry() from public, anon, authenticated;
