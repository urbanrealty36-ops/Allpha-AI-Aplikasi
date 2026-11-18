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
  v_required_tables text[] := array[
    'agent_runtime_sessions','agent_runtime_tasks','agent_runtime_checkpoints',
    'agent_runtime_tool_plans','ai_agents','agent_skills',
    'agent_capabilities','agent_runtime_policies'
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
    array['agent_runtime_checkpoints','task_id'],
    array['agent_runtime_tool_plans','owner_user_id'],
    array['agent_runtime_tool_plans','idempotency_key'],
    array['agent_runtime_tool_plans','request_fingerprint']
  ];
  v_required_functions text[] := array[
    'public.claim_agent_runtime_task(uuid,uuid,uuid,integer)',
    'public.heartbeat_agent_runtime_task(uuid,uuid,uuid,integer,integer)',
    'public.append_agent_runtime_checkpoint(uuid,uuid,uuid,integer,bigint,text,text,text,jsonb)',
    'public.finalize_agent_runtime_task(uuid,uuid,uuid,integer,text,jsonb,text,jsonb)',
    'public.mark_agent_runtime_effect_unknown(uuid,uuid)',
    'public.schedule_agent_runtime_retry(uuid,uuid,uuid,integer,text,integer,jsonb,jsonb)',
    'public.reap_agent_runtime_retry_exhaustion()',
    'public.fail_unclaimed_agent_runtime_task(uuid,uuid,integer,text,uuid)'
  ];
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  foreach v_table in array v_required_tables loop
    if to_regclass('public.' || v_table) is null then
      v_missing_tables := array_append(v_missing_tables, v_table);
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
    if to_regprocedure(v_function) is null then
      v_missing_functions := array_append(v_missing_functions, v_function);
    end if;
  end loop;

  return jsonb_build_object(
    'ready', cardinality(v_missing_tables)=0
      and cardinality(v_missing_columns)=0
      and cardinality(v_missing_functions)=0,
    'missing_tables', to_jsonb(v_missing_tables),
    'missing_columns', to_jsonb(v_missing_columns),
    'missing_functions', to_jsonb(v_missing_functions),
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
