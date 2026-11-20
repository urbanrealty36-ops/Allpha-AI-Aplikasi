-- WP-07: require durable effect evidence before a planned task can become succeeded.
-- Source-only. Apply after the WP-07 atomic Social receipt and worker readiness migrations.
begin;

create or replace function public.guard_agent_runtime_task_success_receipts()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_step jsonb;
  v_step_key text;
  v_tool_key text;
  v_steps jsonb;
begin
  if old.state in ('succeeded','partially_succeeded','failed','cancelled','timed_out','budget_exhausted')
     and new.state is distinct from old.state then
    raise exception 'AGENT_RUNTIME_TERMINAL_STATE_IMMUTABLE' using errcode = '23514';
  end if;

  if new.state <> 'succeeded' or old.state = 'succeeded' then
    return new;
  end if;

  if coalesce(old.effect_outcome, 'none') in ('started','unknown') then
    raise exception 'AGENT_RUNTIME_SUCCESS_REQUIRES_CONFIRMED_EFFECT_OUTCOME'
      using errcode = '23514';
  end if;

  if exists (
    select 1
    from public.agent_runtime_effect_receipts r
    where r.task_id = new.id and r.status <> 'completed'
  ) then
    raise exception 'AGENT_RUNTIME_SUCCESS_HAS_UNRESOLVED_EFFECT_RECEIPT'
      using errcode = '23514';
  end if;

  if new.input_payload->>'_runtime_plan_version' = '1' then
    v_steps := case
      when jsonb_typeof(new.input_payload->'steps') = 'array'
        then new.input_payload->'steps'
      else '[]'::jsonb
    end;

    for v_step in
      select item.value
      from jsonb_array_elements(v_steps) as item(value)
      where item.value->>'tool_key' in ('social.comment','social.reply','social.story_reply')
    loop
      v_tool_key := v_step->>'tool_key';
      v_step_key := 'step:' || coalesce(v_step->>'step_id','');
      if v_step_key = 'step:' or not exists (
        select 1
        from public.agent_runtime_effect_receipts r
        where r.task_id = new.id
          and r.step_key = v_step_key
          and r.status = 'completed'
          and r.actor_user_id = new.owner_user_id
          and r.owner_user_id = new.owner_user_id
          and r.agent_id = new.agent_id
          and r.action_key = v_tool_key
          and r.approval_id is not null
          and r.correlation_id = new.trace_id
          and r.provider_key = 'allpha.social'
          and r.target_reference like 'content:%'
          and r.policy_id is not null
          and r.policy_version is not null
          and r.policy_digest ~ '^[a-f0-9]{64}$'
          and r.external_reference is not null
          and r.evidence_reference is not null
      ) then
        raise exception 'AGENT_RUNTIME_SUCCESS_REQUIRES_APPROVED_SOCIAL_EFFECT_RECEIPT'
          using errcode = '23514';
      end if;
    end loop;
  end if;

  return new;
end;
$$;

do $$
begin
  if not exists (
    select 1 from pg_catalog.pg_trigger
    where tgrelid = 'public.agent_runtime_tasks'::regclass
      and tgname = 'agent_runtime_task_success_receipt_guard'
      and not tgisinternal
  ) then
    create trigger agent_runtime_task_success_receipt_guard
      before update of state on public.agent_runtime_tasks
      for each row execute function public.guard_agent_runtime_task_success_receipts();
  end if;
end;
$$;

create or replace function public.agent_runtime_effect_receipt_guard_readiness()
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_trigger_ready boolean;
  v_function_ready boolean;
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;

  v_trigger_ready := exists (
    select 1 from pg_catalog.pg_trigger
    where tgrelid = 'public.agent_runtime_tasks'::regclass
      and tgname = 'agent_runtime_task_success_receipt_guard'
      and not tgisinternal
  );
  v_function_ready := to_regprocedure(
    'public.guard_agent_runtime_task_success_receipts()'
  ) is not null;

  return jsonb_build_object(
    'ready', v_trigger_ready and v_function_ready,
    'missing_triggers', case when v_trigger_ready then '[]'::jsonb
      else jsonb_build_array('agent_runtime_task_success_receipt_guard') end,
    'missing_functions', case when v_function_ready then '[]'::jsonb
      else jsonb_build_array('public.guard_agent_runtime_task_success_receipts()') end,
    'checked_at', now()
  );
end;
$$;

revoke all on function public.guard_agent_runtime_task_success_receipts()
  from public, anon, authenticated;
revoke all on function public.agent_runtime_effect_receipt_guard_readiness()
  from public, anon, authenticated;
grant execute on function public.agent_runtime_effect_receipt_guard_readiness()
  to service_role;

comment on function public.guard_agent_runtime_task_success_receipts() is
  'Prevents successful terminalization while effects are unknown or any planned Social step lacks a complete owner-bound receipt.';
comment on function public.agent_runtime_effect_receipt_guard_readiness() is
  'Read-only service-role readiness check for the task success/effect receipt invariant.';

commit;
