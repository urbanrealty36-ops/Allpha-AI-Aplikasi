-- ENG-P03: continuously reconcile deletion requests with active legal holds.
-- This is deliberately a governance gate, not a deletion executor: no request
-- may enter processing until an approved source-to-data-class retention map
-- and a complete dependency-cleanup manifest exist.

alter table public.account_lifecycle_events
  drop constraint if exists account_lifecycle_events_event_type_check;
alter table public.account_lifecycle_events
  add constraint account_lifecycle_events_event_type_check
  check (event_type = any (array[
    'export_requested','export_started','export_completed','export_failed',
    'deletion_requested','deletion_cancelled','deletion_scheduled','deletion_started',
    'deletion_blocked','deletion_unblocked','deletion_policy_pending',
    'deletion_completed','deletion_failed'
  ]::text[]));

create or replace function public.evaluate_account_deletion_governance(p_limit integer default 100)
returns table(processed_count integer,blocked_count integer,unblocked_count integer,policy_pending_count integer)
language plpgsql
security definer
set search_path = ''
as $evaluate_deletion_governance$
declare
  v_request public.account_deletion_requests%rowtype;
  v_hold_ids uuid[];
  v_processed integer := 0;
  v_blocked integer := 0;
  v_unblocked integer := 0;
  v_pending integer := 0;
  v_policy_state constant text := 'awaiting_approved_retention_policy_and_dependency_mapping';
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_limit is null or p_limit not between 1 and 500 then
    raise exception 'invalid_deletion_governance_batch_size' using errcode='22023';
  end if;

  for v_request in
    select r.*
      from public.account_deletion_requests r
     where r.status in ('awaiting_policy','scheduled','blocked_legal_hold')
     order by r.requested_at,r.id
     limit p_limit
     for update skip locked
  loop
    v_processed := v_processed + 1;
    select coalesce(array_agg(h.id order by h.created_at,h.id),'{}'::uuid[])
      into v_hold_ids
      from public.account_legal_holds h
     where h.subject_ref=v_request.subject_ref and h.active=true;

    if cardinality(v_hold_ids) > 0 then
      if v_request.status <> 'blocked_legal_hold' then
        update public.account_deletion_requests
           set status='blocked_legal_hold',scheduled_for=null,
               error_code='LEGAL_HOLD_ACTIVE',
               request_metadata=coalesce(request_metadata,'{}'::jsonb) ||
                 jsonb_build_object(
                   'legal_hold_active',true,
                   'active_legal_hold_ids',to_jsonb(v_hold_ids),
                   'deletion_policy_state',v_policy_state,
                   'governance_checked_at',clock_timestamp()
                 ),
               updated_at=clock_timestamp()
         where id=v_request.id;
        insert into public.account_lifecycle_events(
          request_id,user_id,subject_ref,event_type,metadata
        ) values (
          v_request.id,v_request.user_id,v_request.subject_ref,'deletion_blocked',
          jsonb_build_object('reason_code','LEGAL_HOLD_ACTIVE','legal_hold_ids',to_jsonb(v_hold_ids))
        );
        v_blocked := v_blocked + 1;
      end if;
    elsif v_request.status='blocked_legal_hold' then
      update public.account_deletion_requests
         set status='awaiting_policy',scheduled_for=null,error_code=null,
             request_metadata=coalesce(request_metadata,'{}'::jsonb) ||
               jsonb_build_object(
                 'legal_hold_active',false,
                 'active_legal_hold_ids','[]'::jsonb,
                 'deletion_policy_state',v_policy_state,
                 'governance_checked_at',clock_timestamp()
               ),
             updated_at=clock_timestamp()
       where id=v_request.id;
      insert into public.account_lifecycle_events(
        request_id,user_id,subject_ref,event_type,metadata
      ) values (
        v_request.id,v_request.user_id,v_request.subject_ref,'deletion_unblocked',
        jsonb_build_object('reason_code','LEGAL_HOLD_RELEASED','next_gate',v_policy_state)
      );
      v_unblocked := v_unblocked + 1;
    elsif v_request.status in ('awaiting_policy','scheduled') then
      if v_request.status='scheduled' or coalesce(v_request.request_metadata->>'deletion_policy_state','') is distinct from v_policy_state then
        update public.account_deletion_requests
           set status='awaiting_policy',scheduled_for=null,
               error_code=case when v_request.status='scheduled' then 'DELETION_EXECUTION_GATE_INCOMPLETE' else error_code end,
               request_metadata=coalesce(request_metadata,'{}'::jsonb) ||
                 jsonb_build_object(
                   'legal_hold_active',false,
                   'deletion_policy_state',v_policy_state,
                   'governance_checked_at',clock_timestamp()
                 ),
               updated_at=clock_timestamp()
         where id=v_request.id;
        insert into public.account_lifecycle_events(
          request_id,user_id,subject_ref,event_type,metadata
        ) values (
          v_request.id,v_request.user_id,v_request.subject_ref,'deletion_policy_pending',
          jsonb_build_object('gate',v_policy_state)
        );
        v_pending := v_pending + 1;
      end if;
    end if;
  end loop;

  return query select v_processed,v_blocked,v_unblocked,v_pending;
end;
$evaluate_deletion_governance$;

revoke all on function public.evaluate_account_deletion_governance(integer) from public,anon,authenticated;
grant execute on function public.evaluate_account_deletion_governance(integer) to service_role;
