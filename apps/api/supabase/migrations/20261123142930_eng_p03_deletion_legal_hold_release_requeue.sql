-- Restored 2026-11-24 from the canonical live PostgreSQL catalog.
-- Requeue a deletion only after its legal hold is removed or deactivated.
CREATE OR REPLACE FUNCTION private.requeue_account_deletion_after_hold_release()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v_subject_ref text;
begin
  if tg_op='DELETE' then
    v_subject_ref:=old.subject_ref;
  else
    v_subject_ref:=new.subject_ref;
  end if;
  if not exists (
    select 1 from public.account_legal_holds h
    where h.subject_ref=v_subject_ref and h.active=true
  ) then
    update public.account_deletion_requests
       set status='awaiting_policy',error_code=null,updated_at=clock_timestamp()
     where subject_ref=v_subject_ref and status='blocked_legal_hold';
  end if;
  return null;
end;
$function$
;
drop trigger if exists account_deletion_hold_release_requeue on public.account_legal_holds;
create trigger account_deletion_hold_release_requeue after delete or update of active on public.account_legal_holds for each row execute function private.requeue_account_deletion_after_hold_release();

