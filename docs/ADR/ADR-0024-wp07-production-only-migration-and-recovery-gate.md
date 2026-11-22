# ADR-0024 — WP-07 production-only migration and recovery gate

- **Status:** ACCEPTED — Product Owner authorization recorded 2026-11-22; production apply remains gated on recovery evidence
- **Date:** 2026-11-22
- **Owners:** Product Owner (migration policy); Allpha engineering (implementation and evidence)
- **Scope:** WP-07 durable runtime schema and directly dependent WP-06/WP-11 migrations in the canonical Allpha Supabase project `dvdziauyvuhcnqhrrvww`
- **Supersedes:** only the Fixed Phase Plan requirement to validate WP-07 migrations against an existing isolated non-production Supabase target. It does not supersede migration integrity, security, recovery, or worker activation requirements.
- **Related decisions:** `AGENTS.md`; `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md`; Master PRD v3.1.0; `ADR-WP04-003-backup-retention-and-deletion-evidence.md`; `ADR-RAILWAY-001-canonical-runtime-platform.md`.

## 1. Context

The canonical production Supabase project is the only approved database for Allpha. The Product Owner has explicitly authorized a production-only WP-07 migration path and prohibited creation of a staging branch or second database. The prior Fixed Phase Plan checkpoint required an already-existing isolated non-production target. That requirement is no longer a prerequisite for WP-07, but the underlying reason for the gate—avoiding data loss, migration drift, unsafe DDL and unverified recovery—remains mandatory.

The production ledger and repository contain both canonical migrations and source-only migration files. Their filenames, timestamps, dependencies, exact contents and current production schema must be reconciled individually. A file being present in source-only storage is not evidence that it is safe or pending, and a CLI dry-run is not proof that the SQL itself will execute successfully.

## 2. Decision

Use a **production-only, forward-safe, evidence-gated migration procedure** for WP-07. Do not create or use a Supabase staging branch/database for this workstream.

This decision authorizes the procedure and documentation change; it does **not** authorize an immediate blind migration. The first and every subsequent production apply is blocked until the recovery preflight and migration-specific checks below pass.

### 2.1 Recovery preflight (mandatory before any production DDL)

Record and independently verify, through secure provider/account access:

1. Correct project identity: `dvdziauyvuhcnqhrrvww`, organization/account ownership and production environment.
2. Actual Supabase backup/PITR product, enabled state and coverage for the production database.
3. Configured backup/PITR retention, restore-point window, latest available restore point and its timestamp.
4. Whether Storage objects are covered by the same backup policy or require a separate recovery mechanism; record the actual scope rather than assuming database PITR restores object bytes.
5. Documented and owner-accessible recovery procedure, including who can initiate recovery and how the selected restore point is identified.
6. Explicit service recovery objectives (RPO/RTO) or a recorded statement that they remain undefined and therefore limit production acceptance.
7. A migration incident plan: stop conditions, evidence capture, named incident owner, impact assessment, and when a forward repair versus provider PITR restore is appropriate.

Do not place service-role keys, access tokens, database passwords, recovery credentials, or private backup URLs in Git, issue comments, logs, or chat. Store secrets only in approved secret-management surfaces. The evidence record may contain plan/tier names, timestamps, retention values, coverage descriptions and redacted console evidence, but never credentials.

**Gate state at acceptance of this ADR:** recovery evidence has not yet been provided or independently verified in the connected session. Therefore no WP-07 production migration may be applied yet.

### 2.2 Migration identity and ledger integrity

- Treat `apps/api/supabase/migrations` and the remote Supabase migration ledger as canonical.
- Preserve original migration filenames, 14-digit timestamps, exact SQL bytes and SHA-256 checksums for any migration selected for application.
- Never edit, delete, rename, re-timestamp or rewrite an already-applied migration.
- Never delete or rewrite remote ledger rows, and never use `supabase migration repair` to conceal schema drift or mark unapplied SQL as applied.
- Do not bulk-copy `source-only-migrations` into the canonical folder.
- For each source-only candidate, classify it as: already represented by an applied canonical migration; duplicate; superseded; unapplied and eligible; dependency-blocked; or requires a new forward repair. Retain provenance and compare exact content/checksum.
- If a source-only candidate's historical timestamp sorts before already-applied versions, do not silently renumber it. Verify the exact linked CLI dry-run and dependency graph. If the toolchain cannot apply it without violating ordering or dependency semantics, leave it unapplied and create a separately reviewed forward migration with a new version only when that is the correct version-preserving repair. Document the source file and checksum it supersedes; do not pretend the old file was applied.
- Never use the production ledger as a scratchpad. The ledger must reflect SQL actually applied through the canonical path.

### 2.3 Per-migration production preflight

For every candidate migration:

1. Inspect the full SQL and its dependency chain.
2. Run linked migration inventory and the repository workflow's `supabase db push --linked --dry-run`; retain the exact proposed apply list.
3. Compare all referenced tables, columns, types, functions/signatures, enum values, indexes, constraints, triggers, policies, grants and extensions against the live production catalog.
4. Review transaction boundaries, lock acquisition, expected lock duration, table rewrites, backfill volume, uniqueness validation, default volatility, trigger side effects, SECURITY DEFINER search paths and RLS/privilege changes.
5. Confirm idempotency/forward-repair behavior and application compatibility for the deployed API.
6. Reject any unexpected pending migration, timestamp collision, missing dependency, checksum mismatch, destructive operation or unbounded/unknown data rewrite.

A CLI dry-run is a migration-plan check only. Do not execute arbitrary DDL inside a production transaction and roll it back as a substitute for an isolated test; not every DDL or side effect is safely reversible.

### 2.4 Apply protocol

- Apply only a migration whose exact file, checksum, dependency and dry-run position have been reviewed.
- Use the repository's canonical version-preserving GitHub Actions workflow and linked Supabase CLI path; never apply ad hoc SQL copied from chat.
- Apply one migration at a time unless a small dependency-closed batch is explicitly documented and bounded.
- Stop immediately if the actual apply plan differs from the reviewed plan, a lock exceeds its bound, SQL fails, or any post-apply assertion differs from expectation.
- Do not blindly retry a migration after an ambiguous timeout or partial result. Inspect the schema and ledger first.
- Prefer additive/expand-contract schema evolution. Destructive DROP, data-loss transformations, mass backfills, and concurrency/load experiments are excluded from this exception unless separately authorized with a specific recovery plan and evidence.
- No worker, scheduler or event consumer may be enabled during migration execution.

### 2.5 Post-migration assertions

After each migration, verify and retain evidence for:

- exact migration version/name in the production ledger;
- expected tables, columns, types and object definitions;
- RPC signatures, function ownership, EXECUTE grants and SECURITY DEFINER settings;
- constraints, unique indexes, query indexes and triggers;
- RLS enabled state, policy expressions, role grants and owner/tenant isolation;
- row-count and data invariants for any backfill;
- compatibility of deployed FastAPI code with the expanded schema;
- readiness RPC result and dependency status where applicable.

Proceed to the next migration only when every assertion passes. Worker readiness is a separate gate and must remain false until the complete WP-07 readiness contract is satisfied.

## 3. Recovery and rollback policy

1. For additive migrations, the default correction is a reviewed forward-fix migration. Do not attempt a destructive rollback that risks losing concurrent production writes.
2. A migration that changes or removes data must not run under this ADR without a separate decision, explicit impact plan, and verified recovery capability.
3. PITR restore is an incident recovery operation, not a routine migration rollback. It may discard writes made after the selected restore point. It requires an identified incident owner, restore-point selection, impact analysis, service interruption plan and explicit restore authorization.
4. This ADR does not execute or authorize a project restore, pause, failover or data deletion.
5. WP-04 physical deletion and claims about expiry from immutable provider backups remain governed by ADR-WP04-003. This ADR does not waive that policy or permit retention purge.

## 4. Worker activation boundary

The dedicated `allpha-agent-runtime-worker` remains disabled until:

- all required WP-07 migrations are applied and post-migration assertions pass;
- `agent_runtime_worker_schema_readiness()` and every RPC/table/constraint/index/policy dependency return the expected readiness result;
- the actual service-role credential is verified through a secure secret-management view without exposing its value;
- only one canonical consumer owns each queue/event class;
- Railway environment, resource limits, health behavior and secrets are configured server-side;
- targeted real-event lifecycle evidence proves dispatch, claim, lease fencing, heartbeat, retry, cancellation, checkpoint recovery, receipt reconciliation and event replay.

A container build or HTTP health response alone is not runtime acceptance evidence.

## 5. Consequences

- WP-07 can proceed without creating a Supabase staging branch or second database.
- Production migrations are more operationally constrained: every change must be narrowly scoped, forward-safe, individually reviewed and accompanied by live catalog assertions.
- Migration history and checksums remain immutable; source-only files are not applied as a batch.
- Missing backup/PITR evidence remains a hard blocker. The Product Owner has indicated that evidence will be provided through secure access; it has not been verified in this ADR commit.
- No production migration, worker activation or deployment is implied by this decision.

## 6. Status and next action

- **ADR decision:** accepted by Product Owner on 2026-11-22.
- **WP-07 status:** `blocked` pending secure verification of backup/PITR recovery evidence and completion of the per-migration preflight.
- **Next action:** verify the backup/PITR evidence through the secure provider access, then reconcile each candidate migration against the exact production ledger and catalog, run the canonical CLI dry-run, and apply only the reviewed forward-safe migrations in dependency order.
