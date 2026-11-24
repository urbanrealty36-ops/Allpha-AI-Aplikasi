-- ENG-P03: make dependency/policy/hold requeue transitions auditable.
-- Requeue is not deletion approval; the governance worker must re-evaluate all gates.

create or replace function private.requeue_blocked_account_deletion_requests()
returns trigger
language plpgsql
security definer
set search_path = ''
as $function$
begin
  with requeued as (
    update public.account_deletion_requests
       set status='awaiting_policy',
           scheduled_for=null,
           error_code=null,
           request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
             'requeued_at',clock_timestamp(),
             'requeue_reason','DEPENDENCY_POLICY_CHANGED'
           ),
           updated_at=clock_timestamp()
     where status='blocked_dependency'
     returning id,user_id,subject_ref
  )
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  select id,user_id,subject_ref,'deletion_unblocked',
         jsonb_build_object(
           'reason_code','DEPENDENCY_POLICY_CHANGED_REEVALUATION_REQUIRED',
           'source_table',tg_table_name,
           'operation',tg_op
         )
    from requeued;
  return null;
end;
$function$;

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
    v_subject_ref:=old.subject_ref;
    v_hold_id:=old.id;
    v_reference_code:=old.reference_code;
  elsif tg_op='UPDATE' and old.active=true and new.active=false then
    v_subject_ref:=old.subject_ref;
    v_hold_id:=old.id;
    v_reference_code:=old.reference_code;
  else
    return null;
  end if;

  with requeued as (
    update public.account_deletion_requests
       set status='awaiting_policy',
           scheduled_for=null,
           error_code=null,
           request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
             'requeued_at',clock_timestamp(),
             'requeue_reason','LEGAL_HOLD_RELEASED'
           ),
           updated_at=clock_timestamp()
     where subject_ref=v_subject_ref and status='blocked_legal_hold'
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

revoke all on function private.requeue_blocked_account_deletion_requests() from public,anon,authenticated;
revoke all on function private.requeue_account_deletion_after_hold_release() from public,anon,authenticated;
