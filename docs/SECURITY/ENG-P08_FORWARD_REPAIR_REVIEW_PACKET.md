# ENG-P08 Forward-Repair Review Packet (Draft — Not Executable)

- Snapshot: 2026-10-15
- Canonical project: `dvdziauyvuhcnqhrrvww` (production)
- Source: read-only PostgreSQL catalog queries plus all 29 SQL migration files on `main`.
- Status: **Draft for Privacy/Security + Data Platform review. No database writes performed.**
- This file is intentionally outside `apps/api/supabase/migrations/`; its SQL snippets are proposals, not migrations ready to apply.

## A. Object-by-object live inventory and preliminary reconciliation

### A1. Application tables and column contracts

| Live table | Observed columns (ordered) | RLS | Preliminary status |
|---|---|---|---|
| `public.profiles` | `id uuid NOT NULL`, `username text NULL`, `display_name text NOT NULL`, `avatar_url text NULL`, `bio text NOT NULL`, `visibility text NOT NULL DEFAULT 'public'`, `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz NOT NULL DEFAULT now()`, `locale text NOT NULL DEFAULT 'id-ID'`, `account_status text NOT NULL DEFAULT 'active'` | enabled; not FORCE | EXISTS; compare to reconstructed ENG-P02/P03 and forward deactivation RPC. Its table grants are narrower than most other public tables. |
| `public.user_settings` | `user_id uuid NOT NULL`, `theme text NOT NULL DEFAULT 'system'`, `notification_preferences jsonb NOT NULL`, `privacy_settings jsonb NOT NULL`, `updated_at timestamptz NOT NULL DEFAULT now()` | enabled; not FORCE | EXISTS; user self-policy/trigger present; anon table privileges are broader than expected. |
| `public.user_consents` | `id uuid NOT NULL DEFAULT gen_random_uuid()`, `user_id uuid NOT NULL`, `consent_type text NOT NULL`, `policy_version text NOT NULL`, `granted boolean NOT NULL`, `recorded_at timestamptz NOT NULL DEFAULT now()` | enabled; not FORCE | EXISTS; migration contract restricts consent types to terms/privacy/product updates. Must not be reused for knowledge consent. Anon and authenticated table ACLs are broad; RLS still applies to row access but does not justify excess grants. |
| `public.ai_agents` | `id uuid NOT NULL DEFAULT gen_random_uuid()`, `handle text NOT NULL`, `display_name text NOT NULL`, `description text NOT NULL DEFAULT ''`, `avatar_url text NULL`, `persona jsonb NOT NULL DEFAULT '{}'`, `visibility text NOT NULL DEFAULT 'private'`, `status text NOT NULL DEFAULT 'draft'`, `created_by uuid NOT NULL`, `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz NOT NULL DEFAULT now()`, `disclosure text NOT NULL DEFAULT ''`, `boundaries jsonb NOT NULL DEFAULT '{}'` | enabled; not FORCE | EXISTS; 8-argument invoker RPC observed. Anonymous table grants are absent; public discovery needs a separate reviewed projection contract. |
| `public.agent_ownerships` | `agent_id uuid NOT NULL`, `owner_user_id uuid NOT NULL`, `ownership_role text NOT NULL DEFAULT 'owner'`, `status text NOT NULL DEFAULT 'active'`, `created_at timestamptz NOT NULL DEFAULT now()` | enabled; not FORCE | EXISTS; anonymous table privileges are broad despite authenticated-only RLS policies. |
| `public.social_edges` | `id uuid NOT NULL DEFAULT gen_random_uuid()`, `actor_user_id uuid NOT NULL`, `target_user_id uuid NOT NULL`, `edge_type text NOT NULL`, `status text NOT NULL DEFAULT 'active'`, `created_at timestamptz NOT NULL DEFAULT now()` | enabled; not FORCE | EXISTS; anonymous table privileges are broad; repository contains a specific revoke migration not present in ledger. |
| `public.user_interests` | `user_id uuid NOT NULL`, `interest_key text NOT NULL`, `preference text NOT NULL DEFAULT 'interested'`, `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz NOT NULL DEFAULT now()` | enabled; not FORCE | EXISTS; anonymous table privileges are broad. |
| `public.organizations` | expected by repository migrations | not found | NOT DETECTED LIVE; recorded migration versions reference this object. Cause unknown. |
| `public.organization_memberships` | expected by repository migrations | not found | NOT DETECTED LIVE; private helper functions still exist with organization semantics. Cause unknown. |
| `public.audit_events` | expected by repository migrations | not found | NOT DETECTED LIVE; audit writer function remains in public catalog. Cause unknown. |
| `public.agent_skills`, `agent_skill_versions`, `agent_capabilities` | introduced by ENG-P06 migration | not found | NOT DETECTED LIVE; migration is not in ledger. |
| `public.platform_operator_grants`, `platform_operator_audit_events` | introduced by ENG-P06 migration | not found | NOT DETECTED LIVE; migration is not in ledger. |
| `public.agent_knowledge_sources`, `agent_knowledge_jobs`, `agent_knowledge_chunks` | introduced by ENG-P07 migration | not found | NOT DETECTED LIVE; knowledge migration is not in ledger. |
| `storage` policy rows | ENG-P07 proposes bucket/object policies | 0 policies detected in `pg_policies` snapshot | NOT DETECTED LIVE; verify using canonical Storage policy APIs and schema before any change. |

Seven application tables were detected in `public`; Supabase-managed `storage` objects are separate. All seven application tables have RLS enabled, none has FORCE RLS. The inventory query returned 27 public policies and no storage policies.

### A2. Indexes observed on the seven live public tables

| Table | Indexes |
|---|---|
| `agent_ownerships` | `agent_ownerships_one_active_owner`, `agent_ownerships_owner_lookup`, `agent_ownerships_pkey` |
| `ai_agents` | `ai_agents_created_by_idx`, `ai_agents_handle_key`, `ai_agents_pkey`, `ai_agents_public_discovery` |
| `profiles` | `profiles_pkey`, `profiles_username_key` |
| `social_edges` | `social_edges_actor_type_created_idx`, `social_edges_pkey`, `social_edges_target_type_created_idx`, `social_edges_unique` |
| `user_consents` | `user_consents_pkey`, `user_consents_user_id_consent_type_policy_version_key`, `user_consents_user_recorded_idx` |
| `user_interests` | `user_interests_key_idx`, `user_interests_pkey` |
| `user_settings` | `user_settings_pkey` |

No missing index should be created based only on name comparison; compare full `pg_get_indexdef`, predicates, access method, uniqueness and validity before declaring MATCH.

### A3. Constraints

The read-only catalog summary reported 76 CHECK, 9 FK, 7 PK and 4 UNIQUE constraints. This aggregate is not enough to mark individual migrations as matching. The final diff must record each constraint name and exact `pg_get_constraintdef` output, including validation/deferrability where applicable. In particular, verify:
- `agent_ownerships` composite PK and single active-owner partial unique index;
- unique Agent handle;
- unique social-edge identity and edge-type/status checks;
- `user_consents` consent-type check and unique owner/type/policy-version contract;
- all FK targets for ownership, profile, social graph and user-scoped records.

### A4. Functions / overloads / SECURITY DEFINER / grants

The captured public/private application function inventory:

| Schema.function | Identity arguments | SECURITY DEFINER | search_path observed | EXECUTE ACL summary |
|---|---|---:|---|---|
| `private.agent_created_by` | `p_agent_id uuid, p_user_id uuid` | yes | empty | postgres, authenticated |
| `private.has_agent_ownership` | `p_agent_id uuid, p_user_id uuid, p_role text` | yes | empty | postgres, authenticated |
| `private.is_organization_admin` | `target_organization uuid` | yes | empty | postgres, authenticated |
| `private.is_organization_member` | `target_organization uuid` | yes | empty | postgres, authenticated |
| `private.require_agent_owner` | trigger function | yes | empty | postgres only |
| `private.touch_updated_at` | trigger function | no | empty | postgres only |
| `public.audit_organization_created` | trigger function | yes | empty | postgres, service_role |
| `public.create_ai_agent` | 8 args: text,text,text,text,jsonb,text,text,jsonb | no | empty | postgres, authenticated, service_role |
| `public.create_identity_settings_for_existing_user` | trigger function | yes | empty | postgres, service_role |
| `public.create_organization_owner_membership` | trigger function | yes | empty | postgres, service_role |
| `public.enforce_social_edge_policy` | trigger function | yes | empty | postgres, service_role |
| `public.handle_new_auth_user` | trigger function | yes | empty | postgres, service_role |
| `public.rls_auto_enable` | trigger/event function | yes | `pg_catalog` | postgres, service_role |
| `public.set_updated_at` | trigger function | no | empty | PUBLIC, postgres, anon, authenticated, service_role |

The captured `has_function_privilege` query confirms `anon` can execute `public.set_updated_at()`; this is a trigger function and should not normally be directly exposed as a client RPC. Candidate privilege repair must revoke EXECUTE from PUBLIC/anon/authenticated as appropriate while preserving trigger execution semantics and checking any direct application callers. Do not revoke EXECUTE from every public function indiscriminately.

For SECURITY DEFINER functions, an empty configured search_path is a positive hardening signal, but the final review must inspect full function definitions for fully-qualified object references, caller identity derivation, dynamic SQL, ownership and effective EXECUTE privileges. PostgreSQL trigger functions and Supabase-managed `storage.*` functions are not application RPCs; separate them from the application function inventory.

### A5. Triggers observed

Application triggers:
- `ai_agents.ai_agents_require_owner` — deferred constraint trigger calling `private.require_agent_owner()`.
- `ai_agents.ai_agents_touch_updated_at` — BEFORE UPDATE calling `private.touch_updated_at()`.
- `profiles.profiles_create_user_settings` — AFTER INSERT calling `public.create_identity_settings_for_existing_user()`.
- `profiles.profiles_set_updated_at` — BEFORE UPDATE calling `public.set_updated_at()`.
- `social_edges.social_edges_policy_before_write` — BEFORE INSERT/UPDATE of policy-relevant columns calling `public.enforce_social_edge_policy()`.
- `user_interests.user_interests_set_updated_at` — BEFORE UPDATE calling `public.set_updated_at()`.
- `user_settings.user_settings_set_updated_at` — BEFORE UPDATE calling `public.set_updated_at()`.

Supabase-managed storage triggers were also detected on `storage.buckets` and `storage.objects`, including bucket-name validation, lifecycle guard triggers, protected deletes and updated-at behavior. Do not alter managed storage triggers as part of Allpha repair.

### A6. RLS policies and table ACLs

Observed public RLS policies by table:
- `agent_ownerships`: owner delete, self-owner insert, participant select, owner update.
- `ai_agents`: owner delete, creator insert, anonymous public-active select policy, public-or-owned authenticated select, owner update.
- `profiles`: self insert, visible select, self update.
- `social_edges`: actor delete, actor insert, participant select, target acceptance of follow request.
- `user_consents`: self insert/select, client update/delete explicitly false.
- `user_interests`: self select/insert/update/delete.
- `user_settings`: self select/insert/update.

Important: `ai_agents` has an anonymous SELECT RLS policy but captured table ACL says anon has no table privileges, so the policy alone does not make the public projection queryable. Resolve that intentional public discovery contract separately (prefer explicit safe projection/view/API) instead of blindly granting table SELECT.

Captured `has_table_privilege` matrix:

| Table | Role | SELECT | INSERT | UPDATE | DELETE |
|---|---|---:|---:|---:|---:|
| agent_ownerships | anon | yes | yes | yes | yes |
| ai_agents | anon | no | no | no | no |
| profiles | anon | no | no | no | no |
| social_edges | anon | yes | yes | yes | yes |
| user_consents | anon | yes | yes | yes | yes |
| user_interests | anon | yes | yes | yes | yes |
| user_settings | anon | yes | yes | yes | yes |
| agent_ownerships | authenticated | yes | yes | no | no |
| ai_agents | authenticated | yes | yes | yes | no |
| profiles | authenticated | yes | no | no | no |
| social_edges | authenticated | yes | yes | no | yes |
| user_consents | authenticated | yes | yes | yes | yes |
| user_interests | authenticated | yes | yes | yes | yes |
| user_settings | authenticated | yes | yes | yes | yes |

RLS policies can limit rows, but excess grants increase the exposed SQL/API surface and must be reduced to the minimum necessary privileges. Reconcile this matrix against client direct-table use, API routes, triggers and generated API types before deployment.

### A7. Default ACLs

For default objects owned by `postgres` and `supabase_admin` in `public`, the captured default ACLs grant:
- tables: all table privileges to `anon`, `authenticated`, `service_role`;
- functions: EXECUTE to `anon`, `authenticated`, `service_role`;
- sequences: read/write/usage to `anon`, `authenticated`, `service_role`.

This should be corrected by explicit owner-scoped default-privilege changes after review. It must not be confused with current object ACLs; changing default ACLs affects future objects created by the named owners, not already-created objects.

### A8. Migration ledger/source reconciliation

Repository contains 29 SQL files; live migration ledger contains 20 entries. Ledger version/name is not proof of historical SQL checksum. Migration `20261013060000_eng_p04_ai_agent_identity.sql` has the same SHA as `20261013054429_eng_p04_ai_agent_identity.sql` and must be treated as a duplicate file, not an independent migration.

| Migration file | Status from current evidence | Required disposition |
|---|---|---|
| `20261013052302_eng_p02_identity_authorization_baseline.sql` | ledger entry present; organizations and organization_memberships absent live | BLOCKED: reconstructed baseline; don't replay. Recover provenance/object history. |
| `20261013052409_eng_p02_authz_audit_and_org_creation.sql` | ledger entry present; audit_events absent live | BLOCKED: object drift; don't replay. |
| `20261013052557_eng_p02_restrict_security_definer_execution.sql` | ledger entry present | PARTIAL: compare full function ACLs against intended post-state. |
| `20261013052733_eng_p02_move_authz_helpers_to_private_schema.sql` | ledger entry present; organization objects absent | BLOCKED: helpers still exist but dependencies missing. |
| `20261013052744_eng_p02_audit_organization_creation.sql` | ledger entry present; audit_events/organizations absent | BLOCKED: function exists while dependencies are missing; inspect function body and trigger attachment. |
| `20261013053438_eng_p03_human_identity_preferences_and_consent.sql` | ledger entry present; user_settings/user_consents exist | EXISTS: exact constraints, trigger and ACL diff still required. |
| `20261013053502_eng_p03_single_source_profile_visibility.sql` | ledger entry present; user_settings exists | EXISTS: compare full constraint/policy semantics. |
| `20261013054429_eng_p04_ai_agent_identity.sql` | ledger entry present; tables exist | EXISTS: compare columns, checks, FK, policies, triggers and ACLs. |
| `20261013054446_eng_p04_agent_ownership_rls_helpers.sql` | ledger entry present; helper functions exist | EXISTS: compare exact definitions and execute grants. |
| `20261013054513_eng_p04_agent_owner_insert_policy.sql` | ledger entry present; helper exists | EXISTS: compare exact policy/function definition. |
| `20261013054613_eng_p04_agent_creator_rls_fix.sql` | ledger entry present; helper exists | EXISTS: compare exact function body and policy. |
| `20261013054639_eng_p04_agent_disclosure_boundaries.sql` | ledger entry present; disclosure/boundaries columns and RPC exist | EXISTS: compare exact contract. |
| `20261013055121_eng_p04_restrict_agent_table_writes.sql` | ledger entry present | PARTIAL: compare direct table grants against RPC-only writes. |
| `20261013055143_eng_p04_enforce_agent_owner_and_invoker_rpc.sql` | ledger entry present; RPC and deferred owner trigger exist | EXISTS: compare trigger/RPC security and identity semantics. |
| `20261013055318_eng_p04_index_agent_creator.sql` | ledger entry present; index exists | EXISTS: compare exact index definition. |
| `20261013060000_eng_p04_ai_agent_identity.sql` | duplicate SHA of 13054429 | DUPLICATE; never reapply as a distinct migration. |
| `20261013062523_eng_p04_public_passport_anonymous_projection.sql` | ledger entry present | PARTIAL: reconcile policy and grants; anon lacks direct `ai_agents` SELECT. |
| `20261013090730_eng_p02_least_privilege_identity_tenant_grants.sql` | ledger entry present; org/audit tables absent | BLOCKED: grants refer to missing objects; reconstruct intended post-state. |
| `20261013234034_eng_p04_social_graph.sql` | ledger entry present; social tables exist | EXISTS but ACL differs from intended least privilege; prepare narrow forward repair. |
| `20261013234129_eng_p04_social_graph_realtime.sql` | ledger entry present; tables exist | PARTIAL: publication membership not yet verified in this packet. |
| `20261014072435_eng_p05_agent_contract_reconciliation.sql` | ledger entry present; RPC/columns exist | EXISTS: exact definition and grants still require byte/semantic diff. |
| `20261014073741_eng_p06_agent_studio_skills_capabilities.sql` | absent from ledger; target tables absent | NOT DETECTED LIVE; dependency for next ENG-P06 migration. |
| `20261014100000_eng_p01_scoped_account_deactivation_rpc.sql` | absent from ledger; function absent | NOT DETECTED LIVE; candidate forward migration after isolated testing. |
| `20261014130000_eng_p04_revoke_anon_social_graph_privileges.sql` | absent from ledger; anon still has all four table privileges on social tables | NOT DETECTED LIVE; candidate narrow repair after API regression and review. |
| `20261014140000_eng_p06_platform_operator_grants_and_audit.sql` | absent from ledger; target tables absent | NOT DETECTED LIVE; blocked pending isolated validation. |
| `20261014150000_eng_p06_capability_review_audit.sql` | absent from ledger; dependencies absent | BLOCKED by ENG-P06 grants/capabilities. |
| `20261014170000_eng_p07_knowledge_ingestion.sql` | absent from ledger; target tables absent; no storage policies observed | BLOCKED pending privacy contract, data lifecycle and isolated schema validation. |
| `20261014173000_eng_p07_knowledge_fulltext_index.sql` | absent from ledger; chunks table absent | BLOCKED by ENG-P07 schema. |
| `20261014180000_eng_p09_knowledge_job_leases.sql` | absent from ledger; jobs/sources absent | BLOCKED by ENG-P07 objects and ENG-P08 acceptance/approved embedding contract. |

The final reconciliation still needs full definitions of every constraint/index/function, function ownership and all schema/table/column grants. This packet records the object-level inventory available from the captured queries and explicitly marks where full equality is not yet proven.

## B. Proposed repair units (review only; not migrations)

### FR-01 — revoke unexpected anon access to owner-scoped tables

**Candidate scope:** `agent_ownerships`, `social_edges`, `user_consents`, `user_interests`, `user_settings`.  
**Do not include `ai_agents` in this unit:** its public discovery contract requires separate review.  
**Preconditions:** exact project ref; each table exists; current grants match captured matrix or an updated inventory; API/client direct-table use has been inventoried; approved non-production environment is confirmed.  
**Proposed SQL core (not yet approved):**

```sql
REVOKE ALL PRIVILEGES ON TABLE
  public.agent_ownerships,
  public.social_edges,
  public.user_consents,
  public.user_interests,
  public.user_settings
FROM anon;
```

This does not change authenticated grants or RLS policies. It is only a candidate after confirming no legitimate anonymous read/write contract depends on these tables. `user_consents` and personal settings/interests should not be anonymous resources. If anonymous product behavior exists, it must use an explicit safe API/projection rather than direct owner-scoped table grants.

**Regression tests:** anonymous SELECT/INSERT/UPDATE/DELETE all denied for each scoped table; authenticated owner operations still work according to RLS; cross-user operations remain denied; registration and consent flows work; social follow/block flows work; settings/preferences remain owner-only; API endpoints do not regress.

**Recovery:** retain pre-change grant snapshot; if a required operation breaks, restore only the minimum approved privilege for the exact role/table/command and add a scoped RLS/API test before retry. Do not restore blanket ALL grants.

### FR-02 — correct default privileges for future objects

**Candidate scope:** default ACLs for objects created by `postgres` and `supabase_admin` in `public`.  
**Preconditions:** confirm actual migration execution role/owner for each object class and intended grants for future public RPCs; enumerate which future tables/functions/sequences must be exposed; ensure explicit grants can be added in each feature migration.

**Proposed SQL core (not yet approved):**

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM anon;

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM anon;
```

**Important:** this proposal only removes default grants to `anon`; it does not yet address broad default grants to `authenticated` or `service_role`. Review whether `authenticated` defaults should also be narrowed, but avoid breaking explicitly intended direct reads or RPCs. Do not apply this until the migration owner is confirmed and future migrations explicitly grant the required API access.

**Regression tests:** create disposable test table/function/sequence under each actual migration owner in isolated non-production; verify anon has no privileges by default; verify explicit approved grants still work; inspect `pg_default_acl` after migration; remove fixtures only from the isolated test target.

**Recovery:** use `ALTER DEFAULT PRIVILEGES ... GRANT` to restore only the exact previous ACL for the affected owner/object type, or use a reviewed forward repair. Record the before/after `pg_default_acl` snapshot. Rollback does not retroactively change existing object ACLs.

### FR-03 — revoke direct EXECUTE on trigger-only `public.set_updated_at()`

**Candidate SQL core (not yet approved):**

```sql
REVOKE EXECUTE ON FUNCTION public.set_updated_at() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.set_updated_at() FROM anon;
REVOKE EXECUTE ON FUNCTION public.set_updated_at() FROM authenticated;
```

**Preconditions:** verify exact zero-argument signature and confirm no application client invokes this trigger function directly. Trigger execution should continue to work without caller having direct EXECUTE privilege, but this must be verified on isolated non-production.

**Regression tests:** profile/settings/interest updates still trigger timestamp updates; direct RPC attempts by anon/authenticated are denied; no function overload is affected.

**Recovery:** restore EXECUTE only to the specific required role if an approved caller is proven; preferably move caller behavior behind an appropriate API rather than grant trigger-function execution.

### FR-04 — reconstruct missing ENG-P02 objects

**Disposition:** blocked; do not draft runnable DDL until provenance is recovered.  
**Objects:** `organizations`, `organization_memberships`, `audit_events`.  
**Required work:** compare baseline SQL and all dependent helpers/policies/grants/triggers; inspect backup/PITR/catalog history available to Data Platform; establish whether objects were dropped, renamed, relocated, or never present; identify dependent app/API code and live records.  
**Recovery:** no destructive action. Any eventual restore must preserve data and constraints and be an approved forward repair, not blind replay of reconstructed baseline.

### FR-05 — ENG-P06/07 missing tables and knowledge authorization

- ENG-P06 Agent Skills, platform operator grant/audit and capability review migrations remain blocked until schema provenance and existing object inventory are reconciled.
- ENG-P07 knowledge source/job/chunk/storage policies remain blocked pending Privacy/Security + Data Platform approval of consent/grant lifecycle, retention, revocation and derived-data cleanup.
- ENG-P09 job leases remain blocked until ENG-P08 acceptance and approved model/dimension/index contracts.
- Do not reuse general `user_consents`; it covers terms/privacy/product updates only.
- Do not configure the policy provider or add physical consent/grant schema before the canonical contract and reviewers are approved.

## C. Required review checklist

### Privacy/Security
- Approve least-privilege role/command matrix for every exposed table and function.
- Review anonymous public discovery separately from owner-scoped data.
- Verify SECURITY DEFINER ownership, empty/fixed search_path, fully-qualified object references and EXECUTE ACLs.
- Confirm consent is purpose-specific; owner-to-Agent grants are explicit and revocable; private files are never published by implication.
- Approve retention/deletion and revocation propagation to chunks, embeddings, summaries, caches and indexes.
- Confirm audit traces contain identifiers/versions but no private source content.

### Data Platform
- Confirm authoritative schema/migration history and whether missing ENG-P02 objects were dropped/renamed/never applied.
- Confirm actual migration owner(s), default ACL semantics, current catalog snapshot and migration ledger limitations.
- Review each forward repair precondition, lock/transaction impact, repeatability, backup/recovery and verification query.
- Identify an already-existing isolated non-production target and positively verify its Supabase project ref before any migration test. No new project/branch is authorized.
- Confirm official migration workflow and how migration checksum/provenance will be retained.

## D. Gate before any live write

No repair may be applied until all are true:
1. Exact object diff is complete and reviewed.
2. The proposed migration is checked into the canonical migration directory with an explicit version and tests, only after reviewers approve the proposal.
3. Fresh-install and upgrade tests pass; negative authorization and API regression tests pass.
4. An existing isolated non-production target is positively verified; production is not used for destructive or cross-tenant testing.
5. Before-state grants/schema/ledger snapshots and recovery plan are retained.
6. Privacy/Security and Data Platform review is recorded.
7. The user explicitly authorizes applying the tested migration through the official path.

Current disposition: **no database writes; no migration applied; ENG-P08 remains in_progress; ENG-P09 remains blocked.**
