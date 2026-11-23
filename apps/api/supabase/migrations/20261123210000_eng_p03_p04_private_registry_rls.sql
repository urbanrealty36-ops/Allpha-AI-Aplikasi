-- ENG-P03/P04: keep internal registries inaccessible to client roles.
-- No client policy is intentional: these relations are read only by trusted
-- SECURITY DEFINER database routines or the backend service role.
begin;
do $$
begin
  if to_regclass('private.account_export_sources') is null then
    raise exception 'account_export_sources_missing';
  end if;
  if to_regclass('private.user_interest_discovery_index') is null then
    raise exception 'user_interest_discovery_index_missing';
  end if;
end;
$$;
alter table private.account_export_sources enable row level security;
alter table private.user_interest_discovery_index enable row level security;
revoke all on table private.account_export_sources from public, anon, authenticated;
revoke all on table private.user_interest_discovery_index from public, anon, authenticated;
comment on table private.account_export_sources is
  'Internal account export source registry. RLS enabled with no client policies; access is restricted to trusted database routines.';
comment on table private.user_interest_discovery_index is
  'Private interest discovery projection. RLS enabled with no client policies; access is restricted to trusted database routines and backend service role.';
commit;
