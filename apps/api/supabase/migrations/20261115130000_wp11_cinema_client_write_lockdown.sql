-- WP-11/WP-12 security hardening: Cinema business writes are FastAPI-only.
-- Preserve public/owner SELECT policies; revoke direct client DML on canonical catalog tables.
begin;
revoke insert, update, delete, truncate, references, trigger
  on table public.cinema_titles, public.cinema_episodes
  from public, anon, authenticated;
grant select on table public.cinema_titles, public.cinema_episodes
  to anon, authenticated;
drop policy if exists cinema_titles_owner_insert on public.cinema_titles;
drop policy if exists cinema_titles_owner_update on public.cinema_titles;
drop policy if exists cinema_episodes_owner_insert on public.cinema_episodes;
drop policy if exists cinema_episodes_owner_update on public.cinema_episodes;
commit;
