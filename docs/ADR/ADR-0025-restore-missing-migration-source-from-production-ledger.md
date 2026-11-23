# ADR-0025 — Restore missing migration source from the production ledger

**Date:** 2026-11-23  
**Status:** Accepted for source recovery; production apply remains separately gated.

## Context

The production migration ledger contains 147 applied versions while the repository migration directory did not contain source files for 23 of those versions. The isolated ENG-P02 Supabase CLI dry-run correctly refused to proceed because the local migration workspace did not represent the remote applied history.

The production table `supabase_migrations.schema_migrations` retains the original `name` and `statements` for each missing version.

## Decision

Restore each missing source file from the exact SQL statement stored in the corresponding production ledger row. Preserve the original 14-digit version and ledger name. These are historical source files, not placeholders.

No production migration-history row is modified. No `supabase migration repair`, direct ledger INSERT/UPDATE/DELETE, reset, or schema reset is used.

## Recovered versions

- `20261105153601_wp06_agent_social_presence.sql`
- `20261105154718_wp06_transactional_social_approval.sql`
- `20261105154854_wp06_transactional_approval_revoke.sql`
- `20261105154933_wp06_transactional_draft_request.sql`
- `20261105155043_wp06_transactional_policy.sql`
- `20261105155126_wp06_runtime_digest_search_path.sql`
- `20261105155244_wp06_story_dm_agent_conversation_kind.sql`
- `20261105155328_wp06_approval_policy_visibility_guards.sql`
- `20261105160335_wp06_eng_p20_notification_delivery_state.sql`
- `20261105160346_wp06_revoke_notification_delivery_state.sql`
- `20261105160400_wp06_draft_notification_delivery_state.sql`
- `20261105160413_wp06_policy_notification_delivery_state.sql`
- `20261105160510_wp06_story_dm_eng_p20_acceptance_fix.sql`
- `20261115115440_wp11_cinema_client_write_lockdown.sql`
- `20261122114336_eng_p04_polymorphic_social_graph.sql`
- `20261122114556_eng_p04_social_graph_notification_attribution.sql`
- `20261122114707_eng_p04_typed_graph_insert_policy.sql`
- `20261122115225_eng_p04_social_graph_node_counts.sql`
- `20261122120351_eng_p04_social_graph_ownership_lifecycle.sql`
- `20261122152742_eng_p04_social_graph_server_command_boundary.sql`
- `20261122154257_eng_p06_skill_version_rollover_runtime_pinning.sql`
- `20261122204745_eng_p13_cinema_generation_job_artifact_bridge.sql`
- `20261122204926_eng_p13_cinema_generation_link_contract_forward_repair.sql`

## Apply boundary

The ENG-P02 migration workspace must include:
1. Every migration version already recorded in the production ledger, using its recovered/canonical source file.
2. Only the exact ENG-P02 target migration as the sole pending migration.

The other repository-local pending migrations are deliberately excluded from this isolated apply. The dry-run must show only `20261123191500`; otherwise the production apply remains blocked.

## Verification

- All 23 requested ledger rows returned exactly one non-empty SQL statement.
- Each recovered statement ends with a semicolon.
- No known Supabase secret, API-key, database-URL credential, or private-key pattern was found in the recovered SQL.
- The production ledger itself was read only.
