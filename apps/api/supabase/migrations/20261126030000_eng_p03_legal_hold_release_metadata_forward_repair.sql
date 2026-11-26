-- ENG-P03 forward repair: release metadata and audit only after the final active hold is removed.
-- The original trigger requeued requests but left stale legal_hold_active metadata and
-- could emit an unblocked event while another active hold still existed.

create or replace function private.requeue_account_deletion_after_hold_release()
returns trigger
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_subject_ref text;
  v_hold_id uuid;
  v_reference_code text;
begin
  if tg_op='DELETE' then
    if old.active is not true then
      return null;
    end if;
    v_subject_ref:=old.subject_ref;
    v_hold_id:=old.id;
    v_reference_code:=old.reference_code;
  elsif tg_op='UPDATE' and old.active is true and new.active is false then
    v_subject_ref:=old.subject_ref;
    v_hold_id:=old.id;
    v_reference_code:=old.reference_code;
  else
    return null;
  end if;

  -- Releasing one hold must not unblock a request while another hold remains active.
  if exists (
    select 1
      from public.account_legal_holds
     where subject_ref=v_subject_ref
       and active is true
  ) then
    return null;
  end if;

  with requeued as (
    update public.account_deletion_requests
       set status='awaiting_policy',
           scheduled_for=null,
           error_code=null,
           request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
             'requeued_at',clock_timestamp(),
             'requeue_reason','LEGAL_HOLD_RELEASED',
             'legal_hold_active',false,
             'active_legal_hold_ids','[]'::jsonb,
             'legal_hold_released_at',clock_timestamp()
           ),
           updated_at=clock_timestamp()
     where subject_ref=v_subject_ref
       and status='blocked_legal_hold'
     returning id,user_id,subject_ref
  )
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  select id,user_id,subject_ref,'deletion_unblocked',
         jsonb_build_object(
           'reason_code','LEGAL_HOLD_RELEASED_REEVALUATION_REQUIRED',
           'legal_hold_id',v_hold_id,
           'reference_code',v_reference_code
         )
    from requeued;

  return null;
end;
$function$;

revoke all on function private.requeue_account_deletion_after_hold_release() from public,anon,authenticated;
grant execute on function private.requeue_account_deletion_after_hold_release() to service_role;

comment on function private.requeue_account_deletion_after_hold_release() is
  'Requeues blocked deletion requests only after the final active legal hold is removed; clears active-hold metadata and records an auditable release event.';

-- The applied historical migration ledger may predate its current source grant
-- contract. Reassert the service-only execution boundary in this forward repair.
revoke all on function public.evaluate_account_deletion_governance(integer) from public,anon,authenticated;
grant execute on function public.evaluate_account_deletion_governance(integer) to service_role;

comment on function public.evaluate_account_deletion_governance(integer) is
  'Service-role-only governance reconciliation; blocks deletion on active legal holds and advances released requests only to the independent policy/dependency gate.';
