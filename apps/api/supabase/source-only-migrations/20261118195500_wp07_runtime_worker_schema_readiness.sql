-- WP-07: runtime worker startup readiness. This is a read-only schema contract.
-- Source-only: the worker must remain disabled until the canonical migration chain is applied.
begin;

create or replace function public.agent_runtime_worker_schema_readiness()
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_missing_tables text[] := '{}'::text[];
  v_missing_columns text[] := '{}'::text[];
  v_missing_functions text[] := '{}'::text[];
  v_table text;
  v_column text;
  v_column_spec text[];
  v_function text;
  v_proc regprocedure;
  v_missing_privileges text[] := '{}'::text[];
  v_missing_rls text[] := '{}'::text[];
  v_required_tables text[] := array[
    'agent_runtime_sessions','agent_runtime_tasks','agent_runtime_checkpoints',
    'agent_runtime_tool_plans','agent_runtime_execution_events','agent_runtime_effect_receipts',
    'ai_agents','agent_skills',
    'agent_capabilities','agent_runtime_policies',
    'agent_memory_policies','agent_memory_items','agent_memory_events'
  ];
  v_required_columns text[][] := array[
    array['agent_runtime_tasks','id'],
    array['agent_runtime_tasks','owner_user_id'],
    array['agent_runtime_tasks','state'],
    array['agent_runtime_tasks','task_version'],
    array['agent_runtime_tasks','execution_lease_token'],
    array['agent_runtime_tasks','lease_expires_at'],
    array['agent_runtime_tasks','checkpoint_seq'],
    array['agent_runtime_tasks','effect_outcome'],
    array['agent_runtime_tasks','cancel_requested'],
    array['agent_runtime_tasks','execution_attempts'],
    array['agent_runtime_tasks','max_execution_attempts'],
    array['agent_runtime_tasks','next_attempt_at'],
    array['agent_runtime_tasks','input_payload'],
    array['agent_runtime_tasks','request_fingerprint'],
    array['agent_runtime_tasks','trace_id'],
    array['agent_runtime_tasks','event_log'],
    array['agent_runtime_tasks','execution_event_seq'],
    array['agent_runtime_checkpoints','task_id'],
    array['agent_runtime_checkpoints','task_version'],
    array['agent_runtime_checkpoints','sequence'],
    array['agent_runtime_checkpoints','step_key'],
    array['agent_runtime_checkpoints','input_fingerprint'],
    array['agent_runtime_checkpoints','checkpoint_hash'],
    array['agent_runtime_checkpoints','result_payload'],
    array['agent_runtime_tool_plans','owner_user_id'],
    array['agent_runtime_tool_plans','idempotency_key'],
    array['agent_runtime_tool_plans','request_fingerprint'],
    array['agent_runtime_execution_events','task_id'],
    array['agent_runtime_execution_events','owner_user_id'],
    array['agent_runtime_execution_events','sequence'],
    array['agent_runtime_execution_events','task_version'],
    array['agent_runtime_execution_events','trace_id'],
    array['agent_runtime_execution_events','event_type'],
    array['agent_runtime_execution_events','state'],
    array['agent_runtime_execution_events','step_key'],
    array['agent_runtime_execution_events','details'],
    array['agent_memory_policies','owner_user_id'],
    array['agent_memory_policies','consent_version'],
    array['agent_memory_policies','enabled'],
    array['agent_memory_items','owner_user_id'],
    array['agent_memory_items','agent_id'],
    array['agent_memory_items','memory_type'],
    array['agent_memory_items','purpose'],
    array['agent_memory_items','classification'],
    array['agent_memory_items','content'],
    array['agent_memory_items','content_sha256'],
    array['agent_memory_items','policy_version'],
    array['agent_memory_items','retention_expires_at'],
    array['agent_memory_items','search_vector'],
    array['agent_memory_events','owner_user_id'],
    array['agent_memory_events','event_type'],
    array['agent_runtime_effect_receipts','actor_user_id'],
    array['agent_runtime_effect_receipts','owner_user_id'],
    array['agent_runtime_effect_receipts','agent_id'],
    array['agent_runtime_effect_receipts','target_reference'],
    array['agent_runtime_effect_receipts','action_key'],
    array['agent_runtime_effect_receipts','approval_id'],
    array['agent_runtime_effect_receipts','correlation_id'],
    array['agent_runtime_effect_receipts','provider_key'],
    array['agent_runtime_effect_receipts','external_reference'],
    array['agent_runtime_effect_receipts','evidence_reference'],
    array['agent_runtime_effect_receipts','policy_id'],
    array['agent_runtime_effect_receipts','policy_version'],
    array['agent_runtime_effect_receipts','policy_digest']
  ];
  v_required_functions text[] := array[
    'public.claim_agent_runtime_task(uuid,uuid,uuid,integer)',
    'public.heartbeat_agent_runtime_task(uuid,uuid,uuid,integer,integer)',
    'public.append_agent_runtime_checkpoint(uuid,uuid,uuid,integer,bigint,text,text,text,jsonb)',
    'public.append_agent_runtime_execution_event(uuid,uuid,uuid,integer,text,text,text,jsonb)',
    'public.finalize_agent_runtime_task(uuid,uuid,uuid,integer,text,jsonb,text,jsonb)',
    'public.mark_agent_runtime_effect_unknown(uuid,uuid)',
    'public.schedule_agent_runtime_retry(uuid,uuid,uuid,integer,text,integer,jsonb,jsonb)',
    'public.reap_agent_runtime_retry_exhaustion()',
    'public.fail_unclaimed_agent_runtime_task(uuid,uuid,integer,text,uuid)',
    'public.agent_memory_transition(text,uuid,uuid,uuid,jsonb)',
    'public.agent_memory_search(uuid,uuid,uuid[],text,text[],text,text,integer)',
    'public.execute_agent_social_approval_effect(uuid,uuid,uuid,integer,text,text,text,uuid,uuid,text,text,uuid,text,uuid,text,text,text)'
  ];
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  foreach v_table in array v_required_tables loop
    if to_regclass('public.' || v_table) is null then
      v_missing_tables := array_append(v_missing_tables, v_table);
    else
      if not coalesce((select c.relrowsecurity from pg_class c
        where c.oid=to_regclass('public.' || v_table)), false) then
        v_missing_rls := array_append(v_missing_rls, v_table);
      end if;
      if not has_table_privilege('service_role', 'public.' || v_table, 'SELECT') then
        v_missing_privileges := array_append(v_missing_privileges, v_table || ':SELECT');
      end if;
    end if;
  end loop;

  foreach v_column_spec slice 1 in array v_required_columns loop
    v_table := v_column_spec[1];
    v_column := v_column_spec[2];
    if not exists (
      select 1 from information_schema.columns
      where table_schema='public' and table_name=v_table and column_name=v_column
    ) then
      v_missing_columns := array_append(v_missing_columns, v_table || '.' || v_column);
    end if;
  end loop;

  foreach v_function in array v_required_functions loop
    v_proc := to_regprocedure(v_function);
    if v_proc is null then
      v_missing_functions := array_append(v_missing_functions, v_function);
    elsif not has_function_privilege('service_role', v_proc, 'EXECUTE') then
      v_missing_privileges := array_append(v_missing_privileges, v_function || ':EXECUTE');
    end if;
  end loop;

  return jsonb_build_object(
    'ready', cardinality(v_missing_tables)=0
      and cardinality(v_missing_columns)=0
      and cardinality(v_missing_functions)=0
      and cardinality(v_missing_privileges)=0
      and cardinality(v_missing_rls)=0,
    'missing_tables', to_jsonb(v_missing_tables),
    'missing_columns', to_jsonb(v_missing_columns),
    'missing_functions', to_jsonb(v_missing_functions),
    'missing_privileges', to_jsonb(v_missing_privileges),
    'missing_rls', to_jsonb(v_missing_rls),
    'checked_at', now()
  );
end;
$$;

revoke all on function public.agent_runtime_worker_schema_readiness()
  from public,anon,authenticated;
grant execute on function public.agent_runtime_worker_schema_readiness()
  to service_role;

comment on function public.agent_runtime_worker_schema_readiness() is
  'Read-only fail-closed readiness contract for the WP-07 durable worker. It does not start work or mutate runtime rows.';

commit;
