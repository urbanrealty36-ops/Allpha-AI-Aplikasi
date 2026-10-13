-- ENG-P03: human identity preferences, privacy settings, consent history and lifecycle request.
alter table public.profiles
  add column if not exists locale text not null default 'id-ID',
  add column if not exists account_status text not null default 'active';
alter table public.profiles
  drop constraint if exists profiles_locale_check,
  add constraint profiles_locale_check check (locale in ('id-ID','en-US')),
  drop constraint if exists profiles_account_status_check,
  add constraint profiles_account_status_check check (account_status in ('active','deactivation_requested'));

create table if not exists public.user_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  theme text not null default 'system' check (theme in ('light','dark','system')),
  notification_preferences jsonb not null default '{"product_updates":true,"security_alerts":true,"social_activity":true}'::jsonb
    check (jsonb_typeof(notification_preferences) = 'object'),
  privacy_settings jsonb not null default '{"profile_visibility":"public","discoverable_by_username":true}'::jsonb
    check (jsonb_typeof(privacy_settings) = 'object'),
  updated_at timestamptz not null default now()
);

create table if not exists public.user_consents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  consent_type text not null check (consent_type in ('terms_of_service','privacy_policy','product_updates')),
  policy_version text not null check (char_length(policy_version) between 1 and 40),
  granted boolean not null,
  recorded_at timestamptz not null default now(),
  unique (user_id, consent_type, policy_version)
);
create index if not exists user_consents_user_recorded_idx on public.user_consents(user_id, recorded_at desc);

create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = ''
as $$
declare requested_name text;
begin
  requested_name := coalesce(
    nullif(pg_catalog.trim(new.raw_user_meta_data ->> 'display_name'), ''),
    nullif(pg_catalog.trim(new.raw_user_meta_data ->> 'full_name'), ''),
    ''
  );
  insert into public.profiles (id,display_name,locale)
  values (
    new.id,
    pg_catalog.left(requested_name,80),
    case when new.raw_user_meta_data ->> 'locale' = 'en-US' then 'en-US' else 'id-ID' end
  ) on conflict (id) do nothing;
  insert into public.user_settings (user_id) values (new.id) on conflict (user_id) do nothing;
  return new;
end;
$$;

create or replace function public.create_identity_settings_for_existing_user()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.user_settings (user_id) values (new.id) on conflict (user_id) do nothing;
  return new;
end;
$$;
revoke all on function public.create_identity_settings_for_existing_user() from public, anon, authenticated;
drop trigger if exists profiles_create_user_settings on public.profiles;
create trigger profiles_create_user_settings after insert on public.profiles
for each row execute function public.create_identity_settings_for_existing_user();

create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = ''
as $$ begin new.updated_at := pg_catalog.now(); return new; end; $$;
drop trigger if exists user_settings_set_updated_at on public.user_settings;
create trigger user_settings_set_updated_at before update on public.user_settings
for each row execute function public.set_updated_at();

alter table public.user_settings enable row level security;
alter table public.user_consents enable row level security;
drop policy if exists user_settings_select_self on public.user_settings;
create policy user_settings_select_self on public.user_settings for select to authenticated
using (user_id = (select auth.uid()));
drop policy if exists user_settings_insert_self on public.user_settings;
create policy user_settings_insert_self on public.user_settings for insert to authenticated
with check (user_id = (select auth.uid()));
drop policy if exists user_settings_update_self on public.user_settings;
create policy user_settings_update_self on public.user_settings for update to authenticated
using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

drop policy if exists user_consents_select_self on public.user_consents;
create policy user_consents_select_self on public.user_consents for select to authenticated
using (user_id = (select auth.uid()));
drop policy if exists user_consents_insert_self on public.user_consents;
create policy user_consents_insert_self on public.user_consents for insert to authenticated
with check (user_id = (select auth.uid()));
drop policy if exists user_consents_no_client_update on public.user_consents;
create policy user_consents_no_client_update on public.user_consents for update to authenticated
using (false) with check (false);
drop policy if exists user_consents_no_client_delete on public.user_consents;
create policy user_consents_no_client_delete on public.user_consents for delete to authenticated
using (false);

grant select, update on public.profiles to authenticated;
grant select, insert, update on public.user_settings to authenticated;
grant select, insert on public.user_consents to authenticated;
revoke all on function public.create_identity_settings_for_existing_user() from public, anon, authenticated;
