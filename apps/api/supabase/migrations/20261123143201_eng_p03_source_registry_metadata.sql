-- Restored 2026-11-24 from the canonical live PostgreSQL catalog.
-- Persist and synchronize source table/filter metadata for each deletion policy.
alter table public.account_deletion_source_policies
  add column if not exists table_name text,
  add column if not exists filter_kind text,
  add column if not exists owner_columns text[] not null default '{}';
update public.account_deletion_source_policies p
   set table_name=s.table_name,
       filter_kind=s.filter_kind,
       owner_columns=coalesce(s.owner_columns,'{}'::text[])
  from private.account_export_sources s
 where s.source_key=p.source_key;
alter table public.account_deletion_source_policies
  alter column table_name set not null,
  alter column filter_kind set not null;
CREATE OR REPLACE FUNCTION private.sync_account_deletion_source_policy_metadata()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v_source private.account_export_sources%rowtype;
begin
  select * into v_source from private.account_export_sources
   where source_key=new.source_key and enabled=true;
  if not found then raise exception 'account_deletion_source_not_found' using errcode='P0002'; end if;
  new.table_name:=v_source.table_name;
  new.filter_kind:=v_source.filter_kind;
  new.owner_columns:=coalesce(v_source.owner_columns,'{}'::text[]);
  return new;
end;
$function$
;
drop trigger if exists account_deletion_source_policy_metadata_sync on public.account_deletion_source_policies;
create trigger account_deletion_source_policy_metadata_sync before insert or update of source_key on public.account_deletion_source_policies for each row execute function private.sync_account_deletion_source_policy_metadata();

