alter table public.content_schedules drop constraint if exists content_schedules_lease_consistency;
alter table public.content_schedules add constraint content_schedules_lease_consistency check(
 (status='processing' and lease_token is not null and lease_expires_at is not null)
 or (status<>'processing' and lease_token is null and lease_expires_at is null)
);
create or replace function public.content_schedules_touch_updated_at()
returns trigger language plpgsql set search_path=pg_catalog,public
as $$ begin new.updated_at=now();return new;end; $$;
revoke all on function public.content_schedules_touch_updated_at() from public,anon,authenticated;
drop trigger if exists content_schedules_touch_updated_at on public.content_schedules;
create trigger content_schedules_touch_updated_at before update on public.content_schedules
for each row execute function public.content_schedules_touch_updated_at();
