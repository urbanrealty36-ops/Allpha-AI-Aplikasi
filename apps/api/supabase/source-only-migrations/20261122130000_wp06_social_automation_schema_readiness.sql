-- SOURCE ONLY — WP-06 event-consumer schema and privilege readiness.
-- This is a read-only readiness predicate; it does not create a queue or runtime.
begin;

create or replace function public.agent_social_automation_schema_readiness()
returns jsonb
language plpgsql
security definer
set search_path=''
as $$
declare
  v_missing_tables text[] := array[]::text[];
  v_missing_functions text[] := array[]::text[];
  v_missing_columns text[] := array[]::text[];
  v_missing_privileges text[] := array[]::text[];
  v_required_tables text[] := array[
    'agent_social_presence_policies',
    'agent_social_automation_grants',
    'agent_social_automation_events',
    'agent_social_automation_runs',
    'agent_social_control_events',
    'agent_social_audit_events',
    'agent_social_action_approvals'
  ];
  v_table text;
  v_required_privileges text[];
  v_function text;
  v_column record;
begin
  foreach v_table in array v_required_tables loop
    if to_regclass('public.' || v_table) is null then
      v_missing_tables := array_append(v_missing_tables, v_table);
    elsif not coalesce((select c.relrowsecurity from pg_class c
      where c.oid=to_regclass('public.' || v_table)), false) then
      v_missing_privileges := array_append(v_missing_privileges, v_table || ':rls_disabled');
    else
      -- Append-only audit/control projections intentionally require no UPDATE.
      v_required_privileges := case
        when v_table in ('agent_social_control_events','agent_social_audit_events')
          then array['select','insert']::text[]
        else array['select','insert','update']::text[]
      end;
      if exists (
        select 1 from unnest(v_required_privileges) as required(privilege)
        where not has_table_privilege('service_role', 'public.' || v_table, required.privilege)
      ) then
        v_missing_privileges := array_append(v_missing_privileges, v_table || ':service_role_table_privileges');
      end if;
    end if;
  end loop;

  for v_column in
    select * from (values
      ('agent_social_presence_policies','owner_user_id'),
      ('agent_social_presence_policies','agent_id'),
      ('agent_social_presence_policies','is_enabled'),
      ('agent_social_presence_policies','revoked_at'),
      ('agent_social_presence_policies','auto_reply_enabled'),
      ('agent_social_presence_policies','auto_reply_channels'),
      ('agent_social_presence_policies','takeover_active'),
      ('agent_social_presence_policies','version'),
      ('agent_social_automation_events','id'),
      ('agent_social_automation_events','owner_user_id'),
      ('agent_social_automation_events','agent_id'),
      ('agent_social_automation_events','channel'),
      ('agent_social_automation_events','source_table'),
      ('agent_social_automation_events','source_record_id'),
      ('agent_social_automation_events','status'),
      ('agent_social_automation_events','claim_token'),
      ('agent_social_automation_events','lease_expires_at'),
      ('agent_social_automation_events','attempt_count'),
      ('agent_social_automation_events','max_attempts'),
      ('agent_social_automation_events','available_at'),
      ('agent_social_automation_events','event_fingerprint'),
      ('agent_social_automation_events','runtime_task_id'),
      ('agent_social_automation_runs','owner_user_id'),
      ('agent_social_automation_runs','runtime_task_id'),
      ('agent_social_automation_runs','source_event_id'),
      ('agent_social_automation_runs','status')
    ) as required(table_name,column_name)
  loop
    if to_regclass('public.' || v_column.table_name) is not null
       and not exists (
         select 1 from information_schema.columns
         where table_schema='public'
           and table_name=v_column.table_name
           and column_name=v_column.column_name
       ) then
      v_missing_columns := array_append(
        v_missing_columns, v_column.table_name || '.' || v_column.column_name
      );
    end if;
  end loop;

  foreach v_function in array array[
    'public.enqueue_agent_social_automation_event(uuid,uuid,text,text,uuid,uuid,uuid,uuid)',
    'public.claim_agent_social_automation_events(uuid,integer,integer)',
    'public.heartbeat_agent_social_automation_event(uuid,uuid,integer)',
    'public.complete_agent_social_automation_event(uuid,uuid,uuid)',
    'public.fail_agent_social_automation_event(uuid,uuid,text,integer)',
    'public.cancel_agent_social_automation_events(uuid,uuid,text)'
  ] loop
    if to_regprocedure(v_function) is null then
      v_missing_functions := array_append(v_missing_functions, v_function);
    elsif not has_function_privilege('service_role', to_regprocedure(v_function), 'execute') then
      v_missing_privileges := array_append(v_missing_privileges, v_function || ':service_role_execute');
    end if;
  end loop;

  return jsonb_build_object(
    'ready', cardinality(v_missing_tables)=0
      and cardinality(v_missing_columns)=0
      and cardinality(v_missing_functions)=0
      and cardinality(v_missing_privileges)=0,
    'missing_tables', to_jsonb(v_missing_tables),
    'missing_columns', to_jsonb(v_missing_columns),
    'missing_functions', to_jsonb(v_missing_functions),
    'missing_privileges', to_jsonb(v_missing_privileges)
  );
end;
$$;

revoke all on function public.agent_social_automation_schema_readiness() from public, anon, authenticated;
grant execute on function public.agent_social_automation_schema_readiness() to service_role;
comment on function public.agent_social_automation_schema_readiness() is
  'Read-only WP-06 worker activation gate for the canonical social inbox and service-role grants.';

commit;
