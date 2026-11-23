-- ENG-P03: expose the private export-source registry to the authenticated operator API only.
create or replace function public.list_account_deletion_source_registry()
returns table (
  source_key text,
  table_name text,
  filter_kind text,
  owner_columns text[],
  dependency_order integer,
  enabled boolean,
  data_class text,
  deletion_action text,
  policy_version text,
  reason text,
  policy_active boolean,
  approved_by uuid,
  approved_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  return query
    select s.source_key, s.table_name, s.filter_kind, s.owner_columns,
           s.sort_order, s.enabled, p.data_class, p.deletion_action,
           p.policy_version, p.reason, coalesce(p.active, false),
           p.approved_by, p.approved_at
      from private.account_export_sources s
      left join public.account_deletion_source_policies p on p.source_key = s.source_key
     order by s.sort_order, s.source_key;
end;
$$;
revoke all on function public.list_account_deletion_source_registry() from public, anon, authenticated;
grant execute on function public.list_account_deletion_source_registry() to service_role;
