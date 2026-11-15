# WP-07 Manual Review-Only Moderation Adapter — Source Checkpoint

Date: 2026-11-15  
Branch: `main`  
Status: `source_only / acceptance_not_verified`

## Change

Added a built-in `ManualReviewOnlyModerator` implementation to
`apps/api/src/allpha_api/generation_output_moderation.py`.

When no custom moderator factory is configured, the worker can now load this
built-in adapter. It only returns `review_required`; it never returns
`approved` or `rejected`. It requires the approved moderation policy
configuration to contain both:

- `mode: "manual_review_only"`
- `manual_review_only: true`

The existing worker still requires a currently effective database policy row
with `status = approved`. If that policy is absent or expired, the worker
remains idle. When configured, output is stored as a private artifact and
moves into the existing attributed Human review lifecycle. Existing approval
and rejection endpoints/RPCs remain responsible for final decisions,
metering checks, settlement/reconciliation, DM delivery and notifications.

## Safety boundaries

- No moderation decision is inferred from model output or text heuristics.
- The adapter cannot auto-approve content.
- An explicit approved policy is still required; this source change does not
  create or approve a policy row.
- Rejected/review-required outputs are not publicly published.
- No provider, worker, policy or production database configuration was changed.

## Not performed

No tests, builds, lint, typecheck, CI, provider calls, worker activation,
database writes, migration application, staging, browser/device QA or
deployment were performed, per the execution instruction.

## Remaining WP-07 blockers

1. Canonical Supabase still needs the approved, ordered Generation Job and
   external-consumer source migration chain applied through an authorized path.
2. Product/Security/Privacy owner must approve and configure the exact
   manual-review policy version, approval reference, effective time and
   reviewer governance. This source change does not invent these values.
3. Persistent worker deployment/configuration remains inactive until the
   migration and policy prerequisites are approved.
4. Owner reward tariff/settlement policy still requires Product/Finance approval.
5. Multimodal input snapshot and provider adapters remain outstanding; current
   worker execution is text generation only.
6. Authorized integration acceptance remains outstanding and is not replaced
   by source inspection.

WP-07 therefore remains `IN_PROGRESS / ACCEPTANCE_NOT_VERIFIED`. The required
sequence remains WP-07 → WP-06 → WP-11 → WP-12.
