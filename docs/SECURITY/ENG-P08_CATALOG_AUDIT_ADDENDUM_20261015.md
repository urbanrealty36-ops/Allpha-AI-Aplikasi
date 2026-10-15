# ENG-P08 — Live Catalog Audit Addendum (2026-10-15)

## Purpose and boundary

This addendum records a further **read-only** catalog query against the canonical Supabase project `dvdziauyvuhcnqhrrvww` (PostgreSQL 17.6, status previously observed `ACTIVE_HEALTHY`). It supplements, and does not replace, `ENG-P08_CANONICAL_SCHEMA_RECONCILIATION.md` and `ENG-P08_FORWARD_REPAIR_REVIEW_PACKET.md`.

No DDL, DML, grants, migration, Storage policy, or production configuration was changed. These observations are not Privacy/Security or Data Platform approval.

## New catalog evidence

### Function identity, ownership, security mode, ACL and body fingerprints

The query inspected `pg_proc` / `pg_namespace` and recorded each function's identity signature, owner, `prosecdef`, `proconfig`, ACL and `md5(pg_get_functiondef(oid))`.

Observed application functions are owned by `postgres`. The catalog includes the expected public and private functions listed in the forward-repair review packet. The captured body fingerprints include:

| Function signature | SECURITY DEFINER | Catalog config | Body MD5 |
|---|---:|---|---|
| `audit_organization_created()` | yes | empty search_path setting | `ce3925cacf33f0cea3cdd532e1fcb57d` |
| `create_ai_agent(text,text,text,text,jsonb,text,text,jsonb)` | no | empty search_path setting | `0e04b5bac6473978bfcdf904dd45a7b5` |
| `create_identity_settings_for_existing_user()` | yes | empty search_path setting | `8c19bacba53680653d3798cc05b46524` |
| `create_organization_owner_membership()` | yes | empty search_path setting | `5da81b2798d718ca00a6b96fb703cf0d` |
| `enforce_social_edge_policy()` | yes | empty search_path setting | `d269e4ddaaca794e7aad951f0c847f10` |
| `handle_new_auth_user()` | yes | empty search_path setting | `6fbc5be0c1e7fa5caeff7b6bfbb41425` |
| `private.agent_created_by(uuid,uuid)` | yes | empty search_path setting | `2a5ca50d17df2b835efd4b35e65b0e64` |
| `private.has_agent_ownership(uuid,uuid,text)` | yes | empty search_path setting | `5259bacb52fb56bcdda7c0456d487854` |
| `private.is_organization_admin(uuid)` | yes | empty search_path setting | `17b03c3ac3c6f90742e1e7b66961cc10` |
| `private.is_organization_member(uuid)` | yes | empty search_path setting | `83be58e702b6f7735c10362bb3d11f76` |
| `private.require_agent_owner()` | yes | empty search_path setting | `b7623d85cca0b387ee9f4dcbd01cf217` |
| `private.touch_updated_at()` | no | empty search_path setting | `1dd4ad785130e9ca96a692f67f3b56a5` |
| `rls_auto_enable()` | yes | `search_path=pg_catalog` | `6998ea6b4c2480f5d2e34b5dcf3f8d36` |
| `set_updated_at()` | no | empty search_path setting | `7b28ae43a3e645881dcdaef30d4d46ae` |

**Interpretation:** this provides stable fingerprints for a source-to-live comparison, but the comparison is not complete until each live `pg_get_functiondef` is compared with the exact migration definition at the relevant historical migration/repair point. A hash alone does not establish that the live body is correct or safe. Empty `search_path` settings on SECURITY DEFINER functions remain a high-priority manual/source review item; do not alter them mechanically without understanding all object qualification and dependency behavior.

### Column-level grants

The read-only query confirms column-level grants to `anon` on columns in:
- `public.agent_ownerships`: INSERT, REFERENCES, SELECT and UPDATE column privileges.
- `public.ai_agents`: SELECT column privileges.
- `public.social_edges`: INSERT, REFERENCES, SELECT and UPDATE column privileges.
- `public.user_consents`: INSERT, REFERENCES, SELECT and UPDATE column privileges.
- `public.user_interests`: INSERT, REFERENCES, SELECT and UPDATE column privileges.
- `public.user_settings`: INSERT, REFERENCES, SELECT and UPDATE column privileges.

This is additional evidence for FR-01/FR-02 review, not a blanket authorization to revoke privileges. The owner and API access patterns, RLS policies, intended anonymous reads, and column-level grants must be evaluated together. Verify the effective privilege model and regression behavior before approval.

### Realtime publication membership

The current `supabase_realtime` publication exposes these table columns with no publication row filter:

- `public.social_edges`: `id, actor_user_id, target_user_id, edge_type, status, created_at`
- `public.user_interests`: `user_id, interest_key, preference, created_at, updated_at`

This is a catalog snapshot, not proof that clients can or cannot receive particular rows; RLS, Realtime authorization, subscription paths and client usage must also be verified. Confirm product intent and authorization behavior during review. Do not change publication membership as part of a grants repair without an explicit scope decision.

### Storage policy catalog and organization/audit objects

- The SQL query found **zero rows** in `pg_policies` for schema `storage`.
- The queried `public`/`private` table catalog returned no organization/audit-named tables, consistent with the previously recorded missing-object drift.
- Storage API-level bucket/policy verification is still required; the catalog result alone does not prove the effective Storage API policy state.
- The organization/audit objects referenced by historical migrations and extant helper functions still lack verified provenance and a safe forward-repair source.

## Environment gate

A fresh call to Supabase `list_branches` returned an empty list for the canonical project. Therefore **no Supabase development branch is currently evidenced**. Railway staging does not qualify as an isolated database environment until its actual Supabase URL/project reference and credentials are positively verified without exposing secrets.

Do not run migration validation or destructive/cross-tenant tests against the canonical production database. Do not create a new Supabase project or branch as a workaround.

## Remaining reconciliation checklist

- [ ] Compare all 29 repository migration files to the 20 live migration-ledger entries and current physical objects, one object at a time.
- [ ] Compare every live function body, owner, ACL, `SECURITY DEFINER`, and `search_path` against source SQL and identify intentional versus unexplained drift.
- [ ] Finish table-level, column-level, schema-level, function and default ACL reconciliation, including effective privileges.
- [ ] Verify Storage buckets and policies through the Storage API.
- [ ] Verify publication membership and Realtime authorization against intended product behavior.
- [ ] Establish provenance for missing organization/audit objects and determine whether they were intentionally removed, never applied, or lost through drift.
- [ ] Obtain explicit Privacy/Security and Data Platform review decisions for FR-01 through FR-05, with comments/approval evidence.
- [ ] Positively verify an existing isolated non-production environment before applying any candidate migration there.
- [ ] Keep FR proposals outside the canonical executable migrations directory until all required gates pass.

## Status

- ENG-P08: `in_progress`
- ENG-P09: `blocked`
- Database writes: `none`
- FR-01 through FR-05: review required; FR-04/FR-05 remain blocked by provenance/schema dependencies.
- Next step: finish migration-to-catalog object-level diff and provenance, then request/record required reviews. Do not promote repair SQL into the canonical migration directory yet.
