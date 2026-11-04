-- Forward repair for the production-applied auth profile trigger.
-- The original 2026-10-18 migration source was not recoverable. This migration
-- deliberately uses the currently verified database function body and does not
-- claim to recreate the missing historical artifact byte-for-byte.
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path to ''
as $function$
declare
  requested_name text;
begin
  requested_name := coalesce(
    nullif(pg_catalog.btrim(new.raw_user_meta_data ->> 'display_name'), ''),
    nullif(pg_catalog.btrim(new.raw_user_meta_data ->> 'full_name'), ''),
    ''
  );

  insert into public.profiles (id, display_name, locale)
  values (
    new.id,
    pg_catalog.left(requested_name, 80),
    case
      when new.raw_user_meta_data ->> 'locale' = 'en-US' then 'en-US'
      else 'id-ID'
    end
  )
  on conflict (id) do nothing;

  insert into public.user_settings (user_id)
  values (new.id)
  on conflict (user_id) do nothing;

  return new;
end;
$function$;

comment on function public.handle_new_auth_user() is
  'Auth users AFTER INSERT trigger. Forward-repaired from the verified production definition; display_name/full_name are whitespace-trimmed and capped at 80 characters.';
