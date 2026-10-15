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


## E. Exact live index definitions captured (public)

```sql
CREATE UNIQUE INDEX agent_ownerships_one_active_owner ON public.agent_ownerships USING btree (agent_id) WHERE ((ownership_role = 'owner'::text) AND (status = 'active'::text));
CREATE INDEX agent_ownerships_owner_lookup ON public.agent_ownerships USING btree (owner_user_id, status, created_at DESC);
CREATE UNIQUE INDEX agent_ownerships_pkey ON public.agent_ownerships USING btree (agent_id, owner_user_id);
CREATE INDEX ai_agents_created_by_idx ON public.ai_agents USING btree (created_by);
CREATE UNIQUE INDEX ai_agents_handle_key ON public.ai_agents USING btree (handle);
CREATE UNIQUE INDEX ai_agents_pkey ON public.ai_agents USING btree (id);
CREATE INDEX ai_agents_public_discovery ON public.ai_agents USING btree (status, visibility, created_at DESC) WHERE ((status = 'active'::text) AND (visibility = 'public'::text));
CREATE UNIQUE INDEX profiles_pkey ON public.profiles USING btree (id);
CREATE UNIQUE INDEX profiles_username_key ON public.profiles USING btree (username);
CREATE INDEX social_edges_actor_type_created_idx ON public.social_edges USING btree (actor_user_id, edge_type, created_at DESC);
CREATE UNIQUE INDEX social_edges_pkey ON public.social_edges USING btree (id);
CREATE INDEX social_edges_target_type_created_idx ON public.social_edges USING btree (target_user_id, edge_type, created_at DESC);
CREATE UNIQUE INDEX social_edges_unique ON public.social_edges USING btree (actor_user_id, target_user_id, edge_type);
CREATE UNIQUE INDEX user_consents_pkey ON public.user_consents USING btree (id);
CREATE UNIQUE INDEX user_consents_user_id_consent_type_policy_version_key ON public.user_consents USING btree (user_id, consent_type, policy_version);
CREATE INDEX user_consents_user_recorded_idx ON public.user_consents USING btree (user_id, recorded_at DESC);
CREATE INDEX user_interests_key_idx ON public.user_interests USING btree (interest_key);
CREATE UNIQUE INDEX user_interests_pkey ON public.user_interests USING btree (user_id, interest_key);
CREATE UNIQUE INDEX user_settings_pkey ON public.user_settings USING btree (user_id);
```

## F. Exact live application constraint definitions captured

The following is the read-only `pg_get_constraintdef` inventory. All listed constraints were reported validated; the ownership trigger constraint is deferred and initially deferred.

| Table | Constraint | Definition |
|---|---|---|
| agent_ownerships | agent_ownerships_agent_id_fkey | FOREIGN KEY (agent_id) REFERENCES ai_agents(id) ON DELETE CASCADE |
| agent_ownerships | agent_ownerships_owner_user_id_fkey | FOREIGN KEY (owner_user_id) REFERENCES auth.users(id) ON DELETE RESTRICT |
| agent_ownerships | agent_ownerships_ownership_role_check | CHECK (ownership_role = ANY (ARRAY['owner','operator','viewer'])) |
| agent_ownerships | agent_ownerships_pkey | PRIMARY KEY (agent_id, owner_user_id) |
| agent_ownerships | agent_ownerships_status_check | CHECK (status = ANY (ARRAY['active','revoked'])) |
| ai_agents | ai_agents_avatar_url_check | CHECK (avatar_url IS NULL OR char_length(avatar_url) <= 2048) |
| ai_agents | ai_agents_boundaries_check | CHECK (jsonb_typeof(boundaries) = 'object') |
| ai_agents | ai_agents_created_by_fkey | FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE RESTRICT |
| ai_agents | ai_agents_description_check | CHECK (char_length(description) <= 1000) |
| ai_agents | ai_agents_disclosure_check | CHECK (char_length(disclosure) <= 1000) |
| ai_agents | ai_agents_display_name_check | CHECK (char_length(display_name) >= 2 AND char_length(display_name) <= 80) |
| ai_agents | ai_agents_handle_check | CHECK (handle matches ^[a-z0-9_]{3,30}$) |
| ai_agents | ai_agents_handle_key | UNIQUE (handle) |
| ai_agents | ai_agents_persona_check | CHECK (jsonb_typeof(persona) = 'object') |
| ai_agents | ai_agents_pkey | PRIMARY KEY (id) |
| ai_agents | ai_agents_require_owner | TRIGGER DEFERRABLE INITIALLY DEFERRED |
| ai_agents | ai_agents_status_check | CHECK (status = ANY (ARRAY['draft','active','archived'])) |
| ai_agents | ai_agents_visibility_check | CHECK (visibility = ANY (ARRAY['private','public'])) |
| profiles | profiles_account_status_check | CHECK (account_status = ANY (ARRAY['active','deactivation_requested'])) |
| profiles | profiles_avatar_url_length | CHECK (avatar_url IS NULL OR char_length(avatar_url) <= 2048) |
| profiles | profiles_bio_length | CHECK (char_length(bio) <= 500) |
| profiles | profiles_display_name_length | CHECK (char_length(display_name) <= 80) |
| profiles | profiles_id_fkey | FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE |
| profiles | profiles_locale_check | CHECK (locale = ANY (ARRAY['id-ID','en-US'])) |
| profiles | profiles_pkey | PRIMARY KEY (id) |
| profiles | profiles_username_format | CHECK (username IS NULL OR username matches ^[a-z0-9_]{3,30}$) |
| profiles | profiles_username_key | UNIQUE (username) |
| profiles | profiles_visibility_check | CHECK (visibility = ANY (ARRAY['public','private'])) |
| social_edges | social_edges_actor_user_id_fkey | FOREIGN KEY (actor_user_id) REFERENCES auth.users(id) ON DELETE CASCADE |
| social_edges | social_edges_edge_type_check | CHECK (edge_type = ANY (ARRAY['follow','block','mute'])) |
| social_edges | social_edges_follow_status | CHECK (edge_type = 'follow' OR status = 'active') |
| social_edges | social_edges_no_self | CHECK (actor_user_id <> target_user_id) |
| social_edges | social_edges_pkey | PRIMARY KEY (id) |
| social_edges | social_edges_status_check | CHECK (status = ANY (ARRAY['requested','active'])) |
| social_edges | social_edges_target_user_id_fkey | FOREIGN KEY (target_user_id) REFERENCES auth.users(id) ON DELETE CASCADE |
| social_edges | social_edges_unique | UNIQUE (actor_user_id, target_user_id, edge_type) |
| user_consents | user_consents_consent_type_check | CHECK (consent_type = ANY (ARRAY['terms_of_service','privacy_policy','product_updates'])) |
| user_consents | user_consents_pkey | PRIMARY KEY (id) |
| user_consents | user_consents_policy_version_check | CHECK (char_length(policy_version) >= 1 AND char_length(policy_version) <= 40) |
| user_consents | user_consents_user_id_consent_type_policy_version_key | UNIQUE (user_id, consent_type, policy_version) |
| user_consents | user_consents_user_id_fkey | FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE |
| user_interests | user_interests_interest_key_check | CHECK (interest_key matches ^[a-z0-9][a-z0-9._-]{0,79}$) |
| user_interests | user_interests_pkey | PRIMARY KEY (user_id, interest_key) |
| user_interests | user_interests_preference_check | CHECK (preference = ANY (ARRAY['interested','not_interested'])) |
| user_interests | user_interests_user_id_fkey | FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE |
| user_settings | user_settings_notification_preferences_check | CHECK (jsonb_typeof(notification_preferences) = 'object') |
| user_settings | user_settings_pkey | PRIMARY KEY (user_id) |
| user_settings | user_settings_privacy_settings_check | CHECK (jsonb_typeof(privacy_settings) = 'object') |
| user_settings | user_settings_theme_check | CHECK (theme = ANY (ARRAY['light','dark','system'])) |
| user_settings | user_settings_user_id_fkey | FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE |

This exact live inventory must be compared against each creating/altering migration before declaring any constraint MATCH. The query output includes 50 rows including the deferred trigger constraint; the prior aggregate CHECK/FK/PK/UNIQUE counts are a different grouped summary and must not be used to infer migration equality.

## G. Exact policy predicates and remaining proof boundary

Policy predicates observed on application tables:
- `agent_ownerships_delete_owner`: `private.has_agent_ownership(agent_id, auth.uid(), 'owner')`.
- `agent_ownerships_insert_self_owner`: owner equals `auth.uid()`, role owner, status active, and `private.agent_created_by(agent_id, auth.uid())`.
- `agent_ownerships_select_participant`: owner user equals caller or caller is active owner.
- `agent_ownerships_update_owner`: caller is active owner, both USING and WITH CHECK.
- `ai_agents_delete_owner`: caller is active owner of Agent.
- `ai_agents_insert_creator`: `created_by = auth.uid()`.
- `ai_agents_select_public_anon`: visibility public and status active (anon policy; anon has no table SELECT grant in captured matrix).
- `ai_agents_select_public_or_owned`: public active Agent or caller has an ownership row.
- `ai_agents_update_owner`: caller is active owner in USING and WITH CHECK.
- `profiles_insert_self`: `id = auth.uid()`.
- `profiles_select_visible`: visibility public or caller is owner.
- `profiles_update_self`: caller is owner in USING and WITH CHECK.
- `social_edges_insert_actor`: actor is caller and target differs from caller.
- `social_edges_select_participant`: actor is caller, or caller is target of a block, or caller is target of a pending follow request.
- `social_edges_delete_actor`: actor is caller, or caller is target of a pending follow request.
- `social_edges_update_follow_request`: only pending follow request addressed to caller can be updated to active follow.
- `user_consents_insert_self` / `user_consents_select_self`: user ID equals caller.
- `user_consents_no_client_update` / `user_consents_no_client_delete`: explicit false predicate.
- `user_interests` SELECT/INSERT/UPDATE/DELETE policies: user ID equals caller.
- `user_settings` SELECT/INSERT/UPDATE policies: user ID equals caller.

The storage policy inventory query returned zero policies. This finding is limited to the queried `pg_policies` snapshot and must be confirmed against the Storage control-plane before introducing the ENG-P07 private bucket. Storage schema ACLs and Supabase-managed storage triggers are not equivalent to bucket/object row policies.

**Not yet proven:** exact migration-source equality for every live function body, every index/constraint and policy, full function ownership and column-level grants, publication membership, storage bucket state/policies through the Storage API, and historical DDL/PITR provenance for missing organization/audit objects. Until those are closed, this remains a high-coverage inventory plus preliminary reconciliation, not a completed migration audit.


## B. Broader full-repair strategy — parallel evidence tracks, not a single-file queue

The objective is to restore a coherent, least-privilege, reproducible canonical database without replaying historical SQL blindly. Work can proceed in parallel where dependencies permit, while all changes remain read-only until relevant gates pass.

### Track 1 — Establish physical truth and preserve evidence
1. Capture timestamped, read-only catalog snapshots: tables/views, ordered columns/defaults, constraints and validation state, index definitions/validity, RLS/FORCE RLS, policy expressions, triggers, all function overloads/owners/language/SECURITY DEFINER/search_path/full definitions/ACLs, schema/table/column/default privileges, sequences, extensions, publications, and migration ledger.
2. Capture Storage buckets/policies via the Supabase Storage API separately from pg_policies; record Realtime publication membership separately from effective subscription authorization.
3. Store query text, timestamp, project reference, results and limitations in versioned evidence. Redact secrets and personal data; prefer catalog metadata over application rows.
4. Repeat the normalized snapshot at the end to detect concurrent drift. If snapshots differ, suspend classification for affected objects until explained.

**Output:** repeatable before/after catalog evidence, not a migration.

### Track 2 — Reconstruct source provenance and migration lineage
1. Build a migration matrix: filename/version, SHA-256, duplicate hash, ledger presence, SQL targets, dependencies, idempotency, destructive behavior, and whether source is original, reconstructed, or forward repair.
2. Use Git history, commit diffs, pull requests, workflow artifacts and existing authoritative schema/PITR evidence to recover original intent for reconstructed versions. Ledger version/name is not proof of historical SQL bytes.
3. Assign every expected object one state: MATCH, EXISTS BUT DIFFERS, NOT DETECTED LIVE, DUPLICATE, UNRESOLVED PROVENANCE, or NOT APPLICABLE; cite source file/commit and catalog evidence.
4. Do not recreate missing organization/audit objects from names alone. Determine whether they were dropped, never deployed, superseded or omitted from source. If evidence is insufficient, design a reviewed reconstruction contract and data/backfill impact before DDL.

**Output:** source-to-physical lineage and explained difference register.

### Track 3 — Least-privilege and API compatibility
Treat grants as a security workstream separate from missing-schema reconstruction. Calculate effective access from schema USAGE, table/column grants, function EXECUTE, default ACLs, RLS, ownership/BYPASSRLS, API routes and client call sites. Review public RPC exposure and SECURITY DEFINER bodies, not only table grants.
- FR-01: scope anonymous privilege removal to verified objects; decide explicitly whether anonymous reads are intended; preserve authenticated/service-role contracts only when required.
- FR-02: evaluate default ACLs per owner and object type. Changes affect future objects; verify deployment owner and approved RPC contracts first.
- FR-03: search for direct RPC callers before revoking client execution on trigger-only functions; trigger invocation differs from direct EXECUTE.
- Add positive/negative tests for anon, authenticated owner, another authenticated user, service role and unauthorized RPCs. Mocks alone are not live effective-permission evidence.
- If broad anon grants are judged unacceptable before the full repair is ready, record a risk-owner decision for a scoped emergency fix. Do not hotfix production as part of this audit without explicit authorization and the official migration path.

**Output:** role/object/API access matrix, threat assessment, tested least-privilege repair.

### Track 4 — Restore missing domains only after dependency review
Group missing objects by domain and dependency chain:
1. ENG-P02 organization/membership/audit provenance and baseline integrity.
2. ENG-P06 Agent skills/capabilities and operator governance/audit dependencies.
3. ENG-P07 knowledge source/job/chunk tables, full-text index and Storage bucket/policies.
4. ENG-P08 knowledge-specific consent and per-Agent/resource grants, aligned to ADR-0005 and actual canonical permission/privacy services.
5. ENG-P09 job leases and embedding/vector activation only after ENG-P08 acceptance and approved embedding/index contracts.

For each group, decide whether to restore expected objects, adapt source to the verified canonical model, or formally deprecate stale migration contracts. Each choice needs a traceable decision, owner, compatibility plan and dependency map. Never substitute general user_consents for knowledge consent, organization membership for Agent grants, or platform operator grants for user knowledge authorization.

**Output:** approved domain-by-domain forward-repair designs with prerequisites.

### Track 5 — Prove migrations without production mutation
The canonical Supabase project is production. Current branch inventory is empty; the Railway QA-like service is not a valid test target until its database project is positively verified as non-production. No candidate migration can currently be considered execution-validated.
1. Verify an existing isolated non-production project reference, data provenance, access credentials and deployment target without printing secrets.
2. Run fresh-install tests from the reviewed baseline and upgrade tests from a representative drift snapshot. If the baseline cannot be recovered, mark fresh-install equivalence blocked rather than fabricate it.
3. Apply one approved repair at a time through the official migration lifecycle. Record version/hash, command/result, catalog delta, API tests, security negatives, and recovery outcome.
4. Validate precondition failures, idempotency where required, lock/downtime impact, transaction assumptions, recovery readiness, and post-migration grants/policies/functions.
5. Run affected API contracts and two-identity tenant-isolation tests using test-only data in the isolated environment.
6. Re-capture the catalog and compare against the expected target. A non-production pass does not authorize production rollout.

**Output:** reproducible migration proof and post-state diff.

### Track 6 — Review as a decision matrix
Request separate written Privacy/Security and Data Platform decisions for each relevant FR item: APPROVE, APPROVE WITH CONDITIONS, or REJECT, with reviewer role, date, rationale, conditions and evidence links.

| Item | Privacy/Security decision | Data Platform decision |
|---|---|---|
| FR-01 | Anonymous exposure, RLS defense-in-depth, intended public reads | Exact ACL delta and migration mechanism |
| FR-02 | Risk of future default grants and approved RPC surfaces | Object owners, default ACL semantics, migration role |
| FR-03 | Whether function exposure creates an authorization bypass | Trigger/direct-execution compatibility |
| FR-04 | Audit integrity, tenant boundaries, historical data impact | Provenance, dependencies, restoration/reconstruction source |
| FR-05 | Consent scope, grants, revocation/deletion, trace privacy | Canonical schema/service owner, constraints, indexing, retention and migration |

One general approval does not clear all items. Rejection or unmet conditions block dependent work. Record the approval or formal review link; never infer approval from silence or CI.

### Track 7 — Reconcile outcomes and advance status honestly
- Update the single fixed phase plan and this review packet; do not create a parallel phase/status board.
- Keep candidate SQL outside apps/api/supabase/migrations/ until review and isolation gates pass.
- Keep ENG-P08 in_progress until knowledge policy/consent/grant source is verified, reviewed provider implemented, authorization/revocation tests pass in isolated non-production, and acceptance evidence is recorded.
- Keep ENG-P09 blocked until ENG-P08 acceptance and embedding/index/runtime decisions are approved.
- Production rollout requires a separate explicit release decision and the official migration lifecycle.

## C. Current execution decision (2026-10-15)
Proceed with parallel read-only work on Tracks 1–4 and prepare the FR review matrix. Track 5 remains blocked until an existing isolated non-production database is positively verified. See [ENG-P08 Catalog Audit Addendum](ENG-P08_CATALOG_AUDIT_ADDENDUM_20261015.md). No migration is approved for promotion or execution.


## D. Additional migration-lineage finding (2026-10-15)

A direct read of `apps/api/supabase/migrations/20261013052302_eng_p02_identity_authorization_baseline.sql` confirms its header explicitly labels it a **reconstructed baseline for fresh databases**, and says the version was already recorded as applied. Its current source includes `CREATE TABLE IF NOT EXISTS` definitions for organization-domain objects, but this is not proof that the same SQL bytes were historically executed in production.

The live Supabase migration ledger separately contains versions/names:
- `20261013052409` — `eng_p02_authz_audit_and_org_creation`
- `20261013052557` — `eng_p02_restrict_security_definer_execution`
- `20261013052733` — `eng_p02_move_authz_helpers_to_private_schema`
- `20261013052744` — `eng_p02_audit_organization_creation`
- `20261013090730` — `eng_p02_least_privilege_identity_tenant_grants`

The current repository tree was not able to resolve guessed canonical filenames for the first four versions above, while `20261013090730` is a distinct ledger version referenced in phase history. A filename mismatch or absent source path is not sufficient to conclude those migrations never existed: their original source may be under a different path/name, deleted from current `main`, or available only through Git history/artifacts. Their exact SQL bodies remain **UNRESOLVED PROVENANCE** until commit history/tree evidence or an authoritative schema artifact proves the relationship.

### Required provenance recovery steps
1. Enumerate the complete migration directory at the current `main` commit and map every live ledger version to an exact source path by version prefix and content hash; do not infer a match from the suffix alone.
2. Inspect Git history for renamed/deleted migration paths and commits that introduced the reconstructed baseline; preserve the historical blob SHA and commit SHA for each candidate source.
3. If no historical blob exists, record the source as unrecoverable from repository history. Ask the database/platform owner for an existing authoritative dump, migration artifact or PITR-derived schema evidence; do not create a new database to try to reproduce it.
4. Compare the recovered source semantics with the current live catalog and reconstructed baseline. Explain which objects/functions/grants each version was expected to create/change, then determine whether current absence is intentional, drift, or loss.
5. Only after this provenance map is reviewed should FR-04 decide between restoring a known contract, a new versioned forward repair, or formally deprecating an obsolete contract.

This finding strengthens the case for a lineage-first, multi-track repair; it does not authorize replaying any of these historical versions.
