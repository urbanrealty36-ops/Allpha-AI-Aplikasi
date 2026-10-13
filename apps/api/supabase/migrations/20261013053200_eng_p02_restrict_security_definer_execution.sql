-- Restrict callable SECURITY DEFINER functions; trigger functions remain trigger-only.
revoke all on function public.handle_new_auth_user() from public, anon, authenticated;
revoke all on function public.rls_auto_enable() from public, anon, authenticated;
revoke all on function public.is_organization_member(uuid) from public, anon;
revoke all on function public.is_organization_admin(uuid) from public, anon;
grant execute on function public.is_organization_member(uuid) to authenticated;
grant execute on function public.is_organization_admin(uuid) to authenticated;
revoke all on function public.create_organization_owner_membership() from public, anon, authenticated;
