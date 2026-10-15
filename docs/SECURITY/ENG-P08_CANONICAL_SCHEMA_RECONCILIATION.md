# ENG-P08 Canonical Supabase Schema Reconciliation

- **Snapshot date:** 2026-10-15
- **Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`, branch `main`
- **Canonical Supabase:** `AllphaAiAplikasi-db`, project ref `dvdziauyvuhcnqhrrvww`
- **Method:** read-only catalog queries and Supabase inventory APIs; repository migration source inventory.
- **Write status:** **NO DATABASE WRITES, MIGRATIONS, PROVIDERS, PROJECTS OR BRANCHES CREATED.**
- **Purpose:** evidence register for controlled reconciliation. This is not approval to apply any SQL.

## Decision

Do not bulk-apply SQL to the live database. Reconcile physical objects and migration history first; prepare narrowly scoped forward-repair migrations with tests and a recovery strategy; obtain Privacy/Security and Data Platform review where applicable; only then use the official migration path after explicit authorization.

## 1. Live schema snapshot

### Application tables in `public`

| Table | Columns observed | RLS | FORCE RLS |
|---|---|---:|---:|
| `agent_ownerships` | `agent_id`, `owner_user_id`, `ownership_role`, `status`, `created_at` | enabled | no |
| `ai_agents` | `id`, `handle`, `display_name`, `description`, `avatar_url`, `persona`, `visibility`, `status`, `created_by`, `created_at`, `updated_at`, `disclosure`, `boundaries` | enabled | no |
| `profiles` | `id`, `username`, `display_name`, `avatar_url`, `bio`, `visibility`, `created_at`, `updated_at`, `locale`, `account_status` | enabled | no |
| `social_edges` | `id`, `actor_user_id`, `target_user_id`, `edge_type`, `status`, `created_at` | enabled | no |
| `user_consents` | `id`, `user_id`, `consent_type`, `policy_version`, `granted`, `recorded_at` | enabled | no |
| `user_interests` | `user_id`, `interest_key`, `preference`, `created_at`, `updated_at` | enabled | no |
| `user_settings` | `user_id`, `theme`, `notification_preferences`, `privacy_settings`, `updated_at` | enabled | no |

The application table inventory is seven tables. The storage schema also contains Supabase-managed objects; those must not be mistaken for Allpha application tables. The live catalogue query found 27 RLS policies in `public` and none in `storage` for this snapshot. No FORCE RLS was observed on the seven application tables.

### Constraints and extensions

The catalog inventory returned 76 CHECK, 9 foreign-key, 7 primary-key and 4 unique constraints using the query's reported classification. Revalidate counts during the final per-object diff; do not treat aggregate counts as proof that a specific migration matches.

Installed extensions include `vector 0.8.2`, `pgcrypto 1.3`, `pg_stat_statements 1.11`, `plpgsql 1.0`, `supabase_vault 0.3.1` and `uuid-ossp 1.1`. Installed pgvector extension alone does not establish an approved embedding model, dimension, vector table, index strategy or production retrieval pipeline.

## 2. Grants and least-privilege findings

The observed ACLs for application tables include broad privileges for `anon` on:
- `agent_ownerships`
- `social_edges`
- `user_consents`
- `user_interests`
- `user_settings`

The `ai_agents` table did not show an `anon` table ACL in the captured output. `profiles` grants `SELECT` to `authenticated` in the captured ACL.

Default privileges in schema `public` for owners `postgres` and `supabase_admin` include broad table privileges to `anon`, `authenticated` and `service_role`; default function execution to those roles; and default sequence privileges. This is a high-priority least-privilege discrepancy requiring object-by-object impact analysis. Do not apply a broad blanket REVOKE without checking intended API/RPC use, RLS behavior, ownership, grants, and migration dependencies.

The repository migration `20261014130000_eng_p04_revoke_anon_social_graph_privileges.sql` is not present in the live migration ledger; the captured live ACL still gives `anon` broad table privileges on `social_edges` and `user_interests`. Treat this as a candidate forward repair, not permission to apply it immediately.

## 3. Migration ledger versus repository

The live migration ledger returns 20 entries; the repository migration directory contains 29 SQL files. One file, `20261013060000_eng_p04_ai_agent_identity.sql`, has the same SHA-256 as `20261013054429_eng_p04_ai_agent_identity.sql` and is a duplicate candidate, not a second migration to execute.

Eight unique repository migration files were not found in the captured live ledger:

| Migration | Preliminary classification | Dependencies / notes |
|---|---|---|
| `20261014073741_eng_p06_agent_studio_skills_capabilities.sql` | not detected in ledger | Creates `agent_skills` and `agent_capabilities`; objects absent from captured live inventory |
| `20261014100000_eng_p01_scoped_account_deactivation_rpc.sql` | not detected in ledger | `request_account_deactivation()` was not found in targeted function inspection |
| `20261014130000_eng_p04_revoke_anon_social_graph_privileges.sql` | not detected in ledger; live ACL discrepancy observed | Candidate forward privilege repair; requires grants/API regression tests |
| `20261014140000_eng_p06_platform_operator_grants_and_audit.sql` | not detected in ledger | Creates platform operator grant/audit objects absent from captured live inventory |
| `20261014150000_eng_p06_capability_review_audit.sql` | blocked by dependencies | Depends on operator grant/audit objects and `agent_capabilities` |
| `20261014170000_eng_p07_knowledge_ingestion.sql` | not detected in ledger | Knowledge source/job/chunk objects and bucket policies absent from captured live inventory |
| `20261014173000_eng_p07_knowledge_fulltext_index.sql` | blocked by dependency | Requires the knowledge chunks object from ENG-P07 |
| `20261014180000_eng_p09_knowledge_job_leases.sql` | blocked by dependencies and ENG-P08 acceptance | Depends on knowledge tables and unresolved authorization/embedding contracts |

The 20 ledger entries include migrations whose current repository SQL references `organizations`, `organization_memberships` and `audit_events`; those tables were not found in the live catalog snapshot. This is a significant baseline discrepancy. Migration ledger version/name does not prove the exact SQL bytes originally applied, and the reconstructed baseline file must not be blindly replayed.

### Preliminary classification vocabulary

- **MATCH:** live object definition and relevant grants/policies match the reviewed repository migration semantics.
- **EXISTS BUT DIFFERS:** object exists, but columns/constraints/function definition/RLS/grants differ.
- **NOT DETECTED LIVE:** expected object is absent from the inspected catalog.
- **BLOCKED:** comparison or migration action depends on an unresolved object, contract, decision, or approval.
- **DUPLICATE:** repository file content is byte-identical to another migration and must not be replayed as a separate change.

No migration is marked MATCH solely because its version appears in the ledger.

## 4. Reconciliation and repair sequence

1. **Freeze writes:** no mass apply, manual DDL, provider wiring, or ledger edits to make counts appear aligned.
2. **Finish object-level inventory:** compare every application table and column, constraints/indexes, functions and overload signatures, function owner/SECURITY DEFINER/search_path, execute grants, table/schema/default ACLs, RLS policies, triggers, storage buckets/policies, extensions, and migration ledger.
3. **Reconstruct migration provenance:** inspect all 29 repository files and dependencies; compare each live object definition to the SQL's expected post-state. Identify which objects were removed, renamed, moved, or never created. Do not infer why an object is missing.
4. **Prepare narrowly scoped forward repairs:** each repair must have explicit preconditions, idempotency/guard behavior, least-privilege intent, compatibility analysis, fresh-install and upgrade tests, negative authorization tests, and a rollback or forward-recovery procedure.
5. **Review:** Privacy/Security reviews grants/RLS, function privilege boundaries and data exposure; Data Platform reviews physical schema, migration history, ownership and repair safety. Knowledge consent/grants also require review under ADR-0005.
6. **Validate in an already-existing, positively identified isolated non-production database.** No new Supabase project/branch is authorized. The current canonical connector exposes production and no development branches; live production must not be used for destructive tests or cross-tenant isolation tests.
7. **Apply through the official migration workflow only after evidence and explicit authorization.** Apply one reconciled repair at a time, capture the exact migration ID and output, then rerun catalog inventory and relevant application/API tests.
8. **Update the fixed phase plan from evidence.** ENG-P08 remains `in_progress`; ENG-P09 remains `blocked` until ENG-P08 acceptance is evidenced. ENG-P37 remains the cross-domain integration/security/release gate, not a substitute for missing implementation.

## 5. Required validation before any database write

- Preflight asserts expected project ref, schema/object preconditions, current migration ledger and current definitions.
- Fresh-install and upgrade-path tests pass against the intended schema versions.
- Idempotency/re-run behavior is tested where the migration contract requires it.
- Privilege matrix verifies `anon`, `authenticated`, `service_role` and privileged owners for table, sequence, schema and function execution.
- RLS positive and negative tests verify owner isolation, cross-owner rejection and public projection boundaries.
- Function tests inspect overloads, SECURITY DEFINER, fixed safe search_path, caller identity derivation and EXECUTE grants.
- Storage policy tests cover private object access, owner scoping and revocation.
- Rollback/forward-repair procedure is reviewed and tested without risking production data.
- After migration: compare expected object definitions and grants, inspect migration ledger, run API tests and verify no unexpected grants or objects changed.

## 6. Current disposition

- Database writes: **none performed**.
- Bulk migration: **rejected**.
- ENG-P08: **in_progress**; policy implementation is fail-closed while the storage-backed provider is unconfigured.
- ENG-P09: **blocked** pending ENG-P08 acceptance and approved embedding/index contract.
- Privacy/Security and Data Platform review: **required and not yet evidenced as complete**.
- Isolated non-production target: **not verified**; do not run tenant-isolation tests against canonical production.
- This report is a reconciliation work artifact; it does not authorize DDL, provider implementation, migration application, or production release.
