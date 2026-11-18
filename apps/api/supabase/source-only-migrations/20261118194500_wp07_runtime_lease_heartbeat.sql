-- WP-07: lease heartbeat and cancellation observation for planned Agent Runtime tasks.
-- Source-only. Apply only through the canonical migration/release process.
begin;

create or replace function public.heartbeat_agent_runtime_task(
  p_task_id uuid,
  p_owner_user_id uuid,
  p_lease_token uuid,
  p_task_version integer,
  p_lease_seconds integer default 60
) returns setof public.agent_runtime_tasks
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_lease_seconds < 5 or p_lease_seconds > 300 then
    raise exception 'lease_duration_out_of_bounds' using errcode='22023';
  end if;

  return query
  update public.agent_runtime_tasks t
     set lease_expires_at = case
           when t.cancel_requested then t.lease_expires_at
           else now() + make_interval(secs => p_lease_seconds)
         end,
         updated_at = now()
   where t.id = p_task_id
     and t.owner_user_id = p_owner_user_id
     and t.state = 'executing'
     and t.execution_lease_token = p_lease_token
     and t.task_version = p_task_version
     and t.lease_expires_at > now()
  returning t.*;
end;
$$;

revoke all on function public.heartbeat_agent_runtime_task(uuid,uuid,uuid,integer,integer)
  from public, anon, authenticated;
grant execute on function public.heartbeat_agent_runtime_task(uuid,uuid,uuid,integer,integer)
  to service_role;

comment on function public.heartbeat_agent_runtime_task(uuid,uuid,uuid,integer,integer) is
  'Extends only a live, matching Agent Runtime lease. Returns cancel_requested to the worker without renewing a cancelled task.';

commit;
