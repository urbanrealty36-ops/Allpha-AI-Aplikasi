-- DESIGN DRAFT ONLY — NOT A SUPABASE MIGRATION.
-- Do not apply this file to any database.
-- Generate the real migration with `supabase migration new <descriptive-name>`,
-- copy this reviewed SQL into that generated file, then run the approved
-- non-production validation and security-advisor process before any apply.
--
-- Purpose: remove excessive authenticated table/column grants that bypass the
-- intended row-scoped Social Graph access model. Existing RLS policies remain
-- the row authorization layer; this ACL repair removes TRUNCATE and other
-- unnecessary grants. It deliberately does not change policies, data, schema,
-- or global default privileges.

-- Remove table-level grants first (including TRUNCATE, TRIGGER, REFERENCES).
REVOKE ALL PRIVILEGES ON TABLE public.social_edges
  FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES (
  id, actor_user_id, target_user_id, edge_type, status, created_at
) ON TABLE public.social_edges
  FROM PUBLIC, anon, authenticated;

REVOKE ALL PRIVILEGES ON TABLE public.user_interests
  FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES (
  user_id, interest_key, preference, created_at, updated_at
) ON TABLE public.user_interests
  FROM PUBLIC, anon, authenticated;

-- Restore only the privileges needed by the current FastAPI/PostgREST contract.
-- social_edges create sends actor_user_id, target_user_id, edge_type and,
-- for follow requests, status. id and created_at remain database-generated.
GRANT SELECT, DELETE ON TABLE public.social_edges TO authenticated;
GRANT INSERT (actor_user_id, target_user_id, edge_type, status)
  ON TABLE public.social_edges TO authenticated;
GRANT UPDATE (status) ON TABLE public.social_edges TO authenticated;

-- user_interests uses resolution=merge-duplicates with user_id + interest_key
-- as the conflict target; PostgREST upsert may update all submitted columns.
-- RLS still pins user_id to auth.uid(). created_at/updated_at remain
-- client-read-only; updated_at is maintained by the existing database trigger.
GRANT SELECT, DELETE ON TABLE public.user_interests TO authenticated;
GRANT INSERT (user_id, interest_key, preference)
  ON TABLE public.user_interests TO authenticated;
GRANT UPDATE (user_id, interest_key, preference)
  ON TABLE public.user_interests TO authenticated;

-- Reviewed source revision: 2026-10-27; CLI generation is intentionally isolated in the ENG-P04 workflow.
