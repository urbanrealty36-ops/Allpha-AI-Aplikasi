-- ENG-P04 forward repair: remove anonymous grants from user-owned social graph tables.
-- Scope is deliberately limited to the two Social Graph tables. This does not change
-- authenticated grants, RLS policies, Realtime membership, or global default privileges.
-- Apply only through the approved migration path after validating on an isolated non-production database.

revoke all privileges on table public.social_edges from anon;
revoke all privileges (id, actor_user_id, target_user_id, edge_type, status, created_at)
  on table public.social_edges from anon;

revoke all privileges on table public.user_interests from anon;
revoke all privileges (user_id, interest_key, preference, created_at, updated_at)
  on table public.user_interests from anon;
