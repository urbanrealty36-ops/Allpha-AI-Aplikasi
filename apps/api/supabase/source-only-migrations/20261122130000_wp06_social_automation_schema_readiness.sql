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
  v_function text;
begin
  foreach v_table in array v_required_tables loop
    if to_regclass('public.' || v_table) is null then
      v_missing_tables := array_append(v_missing_tables, v_table);
    elsif not coalesce((select c.relrowsecurity from pg_class c
      where c.oid=to_regclass('public.' || v_table)), false) then
      v_missing_privileges := array_append(v_missing_privileges, v_table || ':rls_disabled');
    elsif not has_table_privilege('service_role', 'public.' || v_table, 'select')
       or not has_table_privilege('service_role', 'public.' || v_table, 'insert')
       or not has_table_privilege('service_role', 'public.' || v_table, 'update') then
      v_missing_privileges := array_append(v_missing_privileges, v_table || ':service_role_dml');
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
      and cardinality(v_missing_functions)=0
      and cardinality(v_missing_privileges)=0,
    'missing_tables', to_jsonb(v_missing_tables),
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
