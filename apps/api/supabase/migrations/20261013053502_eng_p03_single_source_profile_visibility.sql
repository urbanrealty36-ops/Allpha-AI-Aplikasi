alter table public.user_settings
  alter column privacy_settings set default '{"discoverable_by_username":true}'::jsonb;
update public.user_settings
set privacy_settings = privacy_settings - 'profile_visibility'
where privacy_settings ? 'profile_visibility';
