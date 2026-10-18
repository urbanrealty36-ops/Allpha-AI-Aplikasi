-- ENG-P12: align audit outcome constraint with operator governance attempts.
-- Preserve fail-closed behavior; this only expands the accepted audit vocabulary.
begin;

alter table public.platform_operator_audit_events
  drop constraint if exists platform_operator_audit_events_outcome_check;

alter table public.platform_operator_audit_events
  add constraint platform_operator_audit_events_outcome_check
  check (outcome = any (array['attempted'::text, 'allowed'::text, 'denied'::text, 'error'::text]));

commit;
