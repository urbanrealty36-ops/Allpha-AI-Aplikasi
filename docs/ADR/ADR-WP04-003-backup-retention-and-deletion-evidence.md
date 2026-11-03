# ADR-WP04-003 — Backup retention and deletion evidence

- Status: PROPOSED — PROVIDER CONFIGURATION EVIDENCE REQUIRED
- Date: 2026-11-03
- Scope: WP-04 physical deletion and recovery

## Context

Content originals and derivatives are stored in the canonical private Supabase Storage bucket. A row/object deletion performed by Allpha does not prove that copies have already expired from provider-managed database/storage backups, point-in-time recovery archives, snapshots, or disaster-recovery copies.

## Proposed policy

1. Allpha performs owner-visible soft deletion and a 30-day recovery period before physical deletion is eligible.
2. Active legal, safety, or regulatory holds block the start of physical deletion.
3. Physical deletion removes canonical originals, derivatives, thumbnails, embeddings/index references and related database rows through bounded, idempotent jobs with a durable receipt.
4. Provider-managed immutable backups remain subject to the actual Supabase project plan and configured backup/PITR retention. No per-object immediate erasure from immutable backups is promised.
5. The project owner must record the actual backup/PITR plan, configured retention duration, restore-point expiry behavior, storage backup scope, and evidence of a successful recovery procedure before production acceptance.
6. Deletion receipts explicitly report provider backup expiry as unverified until that evidence exists. Legal holds must be reviewed before deletion begins; a hold cannot retroactively restore bytes already purged from primary storage.

## Consequences

- Current source receipts use `provider_managed_expiry_not_verified`.
- The configured retention duration is intentionally not guessed or hard-coded because the connected project's actual Supabase plan and backup settings have not been inspected or changed.
- No Supabase backup setting, PITR retention, restore point, or production object was changed by this source implementation.
- WP-04 production acceptance must remain blocked until the owner confirms backup settings and signs off on the operational retention policy.

## Rejected alternatives

- Claiming that a 30-day content recovery window means 30-day backup retention: these are separate lifecycle controls.
- Claiming immediate deletion from immutable backups: not supported by the Storage/Postgres object deletion API.
