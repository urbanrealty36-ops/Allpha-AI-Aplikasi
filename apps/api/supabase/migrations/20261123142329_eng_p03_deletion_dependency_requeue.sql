-- Restored 2026-11-24 from the canonical live PostgreSQL catalog.
-- Requeue blocked deletion requests when dependency/source policy changes.
CREATE OR REPLACE FUNCTION private.requeue_blocked_account_deletion_requests()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  update public.account_deletion_requests
     set status='awaiting_policy',error_code=null,updated_at=clock_timestamp()
   where status='blocked_dependency';
  return null;
end;
$function$
;
drop trigger if exists account_deletion_dependency_rule_requeue on public.account_deletion_dependency_rules;
create trigger account_deletion_dependency_rule_requeue after insert or update or delete on public.account_deletion_dependency_rules for each statement execute function private.requeue_blocked_account_deletion_requests();

drop trigger if exists account_deletion_source_policy_requeue on public.account_deletion_source_policies;
create trigger account_deletion_source_policy_requeue after insert or update or delete on public.account_deletion_source_policies for each statement execute function private.requeue_blocked_account_deletion_requests();

