-- ENG-P03 forward repair: include canonical ENG-P04 Passion/Habit data in account exports.
-- These owner-scoped records are first-party personal data; the derived private
-- discovery index is intentionally excluded because it is rebuildable from source preferences.

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
  ('interest_graph_signals','user_interest_graph_signals','owner_columns',array['user_id']::text[],48,true),
  ('interest_graph_signal_events','user_interest_graph_signal_events','owner_columns',array['user_id']::text[],49,true)
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
