-- ENG-P03/P04 forward compatibility guard: the account export manifest must
-- include the canonical owner-scoped Passion/Habit signal state and event history.
-- The P04 ontology migration seeds these sources on fresh installs; this migration
-- repairs older upgraded installs and fails closed if their mapping is inconsistent.

do $$
begin
  if to_regclass('public.user_interest_graph_signals') is null
     or to_regclass('public.user_interest_graph_signal_events') is null then
    raise exception 'account_export_interest_graph_source_table_missing';
  end if;
  if not exists (
    select 1 from information_schema.columns
     where table_schema='public' and table_name='user_interest_graph_signals'
       and column_name='user_id'
  ) or not exists (
    select 1 from information_schema.columns
     where table_schema='public' and table_name='user_interest_graph_signal_events'
       and column_name='user_id'
  ) then
    raise exception 'account_export_interest_graph_owner_column_missing';
  end if;
end;
$$;

insert into private.account_export_sources(
  source_key,table_name,filter_kind,owner_columns,sort_order,enabled
) values
  ('interest_graph_signals','user_interest_graph_signals','owner_columns',array['user_id']::text[],44,true),
  ('interest_graph_signal_events','user_interest_graph_signal_events','owner_columns',array['user_id']::text[],45,true)
on conflict (source_key) do nothing;

do $$
begin
  if not exists (
    select 1 from private.account_export_sources
     where source_key='interest_graph_signals'
       and table_name='user_interest_graph_signals'
       and filter_kind='owner_columns'
       and owner_columns=array['user_id']::text[]
       and enabled
  ) or not exists (
    select 1 from private.account_export_sources
     where source_key='interest_graph_signal_events'
       and table_name='user_interest_graph_signal_events'
       and filter_kind='owner_columns'
       and owner_columns=array['user_id']::text[]
       and enabled
  ) then
    raise exception 'account_export_interest_graph_source_registry_conflict';
  end if;
end;
$$;
