-- ENG-P03: retain a fail-closed compatibility response for legacy checkout callers.
-- The 3-argument RPC always raises BILLING_STRIPE_ENVIRONMENT_REQUIRED; only the
-- 4-argument RPC can create orders and it requires an explicit test/live environment.
grant execute on function public.billing_create_order(uuid,text,text) to service_role;
