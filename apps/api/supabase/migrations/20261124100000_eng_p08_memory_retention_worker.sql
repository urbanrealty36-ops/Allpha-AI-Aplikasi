-- ENG-P08: bounded, lease-safe batch expiry for owner-private Memory.
-- The worker is separately gated; this migration only defines a service-only RPC.
create or replace function public.expire_agent_memory_items_batch(p_limit integer)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_expired integer := 0;
begin
  if p_limit is null or p_limit < 1 or p_limit > 500 then
    raise exception 'MEMORY_EXPIRY_BATCH_LIMIT_INVALID' using errcode = '22023';
  end if;

  with due as (
    select i.id
      from public.agent_memory_items i
     where i.status in ('pending', 'active')
       and i.retention_expires_at <= clock_timestamp()
     order by i.retention_expires_at asc, i.id asc
     limit p_limit
     for update skip locked
  ),
  expired as (
    update public.agent_memory_items i
       set status = 'expired',
           content = '',
           pinned_at = null,
           content_sha256 = encode(extensions.digest('', 'sha256'), 'hex'),
           source_ref = '{}'::jsonb,
           provenance = '{"retention":"expired"}'::jsonb,
           confidence = null,
           updated_at = clock_timestamp()
      from due
     where i.id = due.id
    returning i.id, i.owner_user_id, i.agent_id, i.policy_id,
              i.memory_type, i.purpose, i.classification, i.version
  ),
  events as (
    insert into public.agent_memory_events (
      owner_user_id, owner_subject_hash, agent_id, policy_id, item_id,
      actor_user_id, event_type, details
    )
    select e.owner_user_id,
           encode(extensions.digest(e.owner_user_id::text, 'sha256'), 'hex'),
           e.agent_id, e.policy_id, e.id, null, 'item_expired',
           jsonb_build_object(
             'memory_type', e.memory_type,
             'purpose', e.purpose,
             'classification', e.classification,
             'version', e.version,
             'retention_expired', true
           )
      from expired e
    returning id
  )
  select count(*) into v_expired from expired;

  return jsonb_build_object('expired_count', v_expired, 'batch_limit', p_limit);
end;
$function$;

revoke all on function public.expire_agent_memory_items_batch(integer)
  from public, anon, authenticated;
grant execute on function public.expire_agent_memory_items_batch(integer)
  to service_role;

comment on function public.expire_agent_memory_items_batch(integer) is
  'Expires at most p_limit due owner-private Memory items, scrubs content and provenance, and records a pseudonymous system audit event.';
