# WP-06 — Human + AI Agent Co-authored Social Presence (Source Implementation Checkpoint)

**Date:** 2026-11-05  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi` · branch `main`  
**Status:** `in_progress`  
**Execution mode:** source-level only, with Product Owner instruction to skip account QA.

## Product Owner direction and gate disposition

The Product Owner explicitly directed to proceed to WP-06 and skip Account QA. This is recorded as a waiver of the account/device QA prerequisite for beginning WP-06 source implementation. It does **not** retroactively change WP-05 to `acceptance_passed`; WP-05 remains `in_progress` / runtime acceptance not verified. WP-06 is therefore opened for source implementation only. No account/device QA, staging, tests, builds, lint, typecheck, CI, migration execution/application, Supabase mutation, provider calls or deployment were performed.

## PRD / phase traceability

- WP-06: Human Owner and Agent author identity; attribution/disclosure; owner policy; Agent post capabilities; approval thresholds; audit; revoke/suspend/kill switch.
- Related canonical domains: Human Identity, AI Agent Identity/Persona/Capability, Agent Runtime, Content Graph, Feed Engine, Social Graph, Notification.
- Canonical boundaries retained: FastAPI owns business decisions; Supabase PostgreSQL is durable source of truth; Agent Runtime tasks must be completed and bound to the authenticated owner + Agent; Web and Native consume the Feed API; push delivery remains owned by ENG-P20.

## Source changes

| File | Change |
|---|---|
| `apps/api/supabase/migrations/20261105150000_wp06_agent_social_presence.sql` | Adds owner-scoped Agent social policies and durable action approval records; links approval to completed Agent Runtime task; enables RLS and denies client table privileges; grants backend service role only. |
| `apps/api/src/allpha_api/agent_social_api.py` | Adds owner policy read/write, completed-runtime-task-bound co-authored draft creation, pending approval listing, approve/reject, and approval revocation. Ownership, active Agent status, policy action allowlist, runtime task owner/Agent/succeeded state, content version and approval state are checked server-side. |
| `apps/api/src/allpha_api/main.py` | Mounts the WP-06 API router. |
| `apps/api/src/allpha_api/feed_api.py` | Projects explicit `authorship` metadata for co-authored content; private provenance is removed from the Feed response. |
| `apps/web/app/feed/page.tsx`, `apps/web/lib/reference-store.ts`, `apps/web/components/reference-ui/FeedView.tsx` | Passes and displays Human + AI Agent co-author disclosure in the Web Feed. |
| `apps/client/App.tsx` | Adds Native Feed attribution contract and disclosure rendering. |

## Guardrails

- Client-supplied owner IDs are not trusted; owner identity is derived from authenticated FastAPI context.
- Agent must be active and have an active owner relationship.
- A draft must reference a succeeded Agent Runtime task belonging to the same owner and Agent, with a completion timestamp and structured output.
- Owner policy must be enabled and explicitly allow the action.
- Every action currently requires Human approval, including the configured `high_risk_only` mode; this is deliberately conservative until a canonical risk classification/threshold policy is fully represented.
- Approval is version-bound to the draft. Changed drafts cannot use stale approval.
- Disabling the owner policy revokes pending/approved approvals; approval decision rechecks the current policy.
- Approval is not publication. Approved drafts still proceed through existing content moderation and publishing lifecycle.
- Feed exposes a minimal disclosure projection; internal provenance is not returned.
- Approval events create an idempotent in-app notification; Expo push remains downstream and is not invoked here.
- The existing Agent Runtime remains the only task execution authority. This API does not execute a model or tool itself.

## Known gaps / not completed

- No dedicated Web or Native owner policy editor / approval inbox UI has been added yet; the API contracts and Feed disclosure are present.
- Comment/reply/repost/story/live action coverage remains limited to the current post/story policy schema; comments, replies, repost, video and Live require follow-on vertical slices.
- No dedicated operator audit event stream or admin review surface has been added for WP-06 beyond the durable approval decision record.
- Runtime task output-to-content body binding is not yet cryptographically or structurally verified; the task must be succeeded and owner/Agent matched, but the client still supplies the draft body. This must be closed before autonomous Agent publishing is enabled.
- No migration or runtime operation has been executed; the SQL is source-only.
- No tests, CI, builds, browser/device QA or account QA were run, by instruction.

## Commit trail

- `4ff226c414e93647bf01e8e30810e561b4de8d5b` — initial WP-06 policy/approval schema.
- `28d6325295f07b53e0f1fa6df932de288562888d` — WP-06 API routes.
- `b4306721610b6aafb9d3a78834a9737e51db49c7` — API router mount.
- `159570938e1c049f49fe5ee0d079ad3196a1bfb7` — completed Agent Runtime task binding.
- `3da7be15203060b4ff16d74f98c7e5fbdf717529` — Feed authorship projection.
- `b4301a9777af14b164f0cc2e7d197ed0b01ad8e9` — remove private provenance from Feed payload.
- `bdb7b401658391d9266c2aa909093b2e05dfc308` — Web Feed attribution type.
- `b1323510eb5f93b74c91c66741a9c9f55d6009a2` — shared Feed card model.
- `4e2cbc8b27294e36f7bbe5b92ac5c1b419d54d7c` — Web Feed API mapping.
- `9c477737c9b1755b9788a7e9b7804c47dd95c6e3` — Web Feed disclosure rendering.
- `74872d87d94a8bf71c2f8b0077095d1fc1274ded` — Native Feed disclosure rendering.
- `c6bf76482d927addc99a491b6b637dcfacd1f68f` — approval schema links to Agent Runtime task.
- `e0edc0a5a4415dd61e1025e101c57f39d0eb344c` — runtime provenance, approval revocation and policy recheck hardening.

## Status

WP-06 is `in_progress` (source implementation underway), not `implemented`, `integration_verified`, or `acceptance_passed`. WP-05 remains `in_progress` with account/device acceptance skipped by Product Owner instruction. No runtime or production readiness is claimed.

## Next source-only work

1. Close runtime task output-to-content binding so the content body must be derived from the exact completed task output, not independently client supplied.
2. Add owner policy and pending approval UI to Web and Native, including loading/empty/error/disabled/revoked states.
3. Extend approved action types to replies/reposts/stories only with resource-scoped authorization and content moderation parity.
4. Add durable audit and notification event contracts for approval/revocation, while retaining ENG-P20 as the sole push dispatcher.
5. Update WP-06 traceability and report each surface as `CHANGE`, `INTEGRATE`, or `NOT AFFECTED`.
