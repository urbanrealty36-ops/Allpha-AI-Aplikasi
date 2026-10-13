create or replace function public.audit_organization_created()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.audit_events(actor_user_id, organization_id, action, resource_type, resource_id, metadata)
  values ((select auth.uid()), new.id, 'organization.created', 'organization', new.id::text, jsonb_build_object('slug', new.slug));
  return new;
end;
$$;
revoke all on function public.audit_organization_created() from public, anon, authenticated;
drop trigger if exists organizations_audit_created on public.organizations;
create trigger organizations_audit_created after insert on public.organizations
for each row execute function public.audit_organization_created();
