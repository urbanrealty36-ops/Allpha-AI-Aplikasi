-- ENG-P03 forward repair: enforce least-privilege grants on user-owned settings.
-- Live schema inventory found broad table-level grants for anon/authenticated,
-- including TRUNCATE. RLS is not a substitute for revoking unnecessary table
-- privileges. Keep trusted service_role access unchanged.
-- Source-only until reviewed and applied through the approved migration process.

revoke all privileges on table public.user_settings from public, anon, authenticated;
revoke all privileges (user_id, theme, notification_preferences, privacy_settings, updated_at)
  on table public.user_settings from anon, authenticated;

-- API-backed user settings are row-scoped by the existing RLS policies.
-- Clients can read their own settings and write only editable preference fields.
grant select on table public.user_settings to authenticated;
grant insert (user_id, theme, notification_preferences, privacy_settings)
  on table public.user_settings to authenticated;
grant update (theme, notification_preferences, privacy_settings)
  on table public.user_settings to authenticated;
