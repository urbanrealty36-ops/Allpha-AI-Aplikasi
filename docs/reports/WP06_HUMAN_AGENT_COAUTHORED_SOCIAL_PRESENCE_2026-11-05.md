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

## Follow-on source checkpoint — 2026-11-05

- agent_social_api.py: draft body is now derived from completed Agent Runtime output rather than accepted from the client. A bounded text extraction accepts content, text, body, or generated_text; private provenance stores a SHA-256 digest.
- The policy/API action allowlist now names post, comment, reply, repost suggestion and story draft actions. The existing approval migration was corrected to declare runtime_task_id before its uniqueness constraint and includes an optional target content reference.
- Added agent_social_audit_events source schema and an operator-only audit read endpoint guarded by platform:security.audit.read.
- Added Web route /agent-social for owner policy editing and approval/revocation. It uses the existing Allpha Web reference-ui visual language; exact parity against the separate ADR-0003 reference repository remains unverified because that repository could not be enumerated with the active connector search.
- This is still a partial source slice. Native UI/navigation, Super Admin audit page, event-backed audit writes, action-specific comment/reply/repost/story lifecycle integration, canonical notification outbox integration, and schema/output contract reconciliation remain outstanding.
- No tests, builds, CI, QA, migration application, database mutation, staging or deployment were run. WP-06 remains in_progress; no acceptance status is claimed.

## Web, Native and Super Admin follow-on — 2026-11-05

- Native owner controls and approval inbox are implemented in `apps/client/components/AgentSocialControls.tsx` and wired into `apps/client/App.tsx` as the `agentSocial` tab. Both use authenticated FastAPI calls for policy, decisions and revocation.
- Super Admin audit review is implemented at `apps/super-admin/app/agent-social-audit/page.tsx`; it authenticates the operator and requests the operator-scoped audit route. No tokens are persisted to browser storage.
- API audit writes now cover policy create/update/disable, draft request, approval approve/reject and revocation. These are separate database writes after the business mutation; without a transactional RPC, failure between the writes can leave an unaudited committed mutation. This is an explicit unresolved consistency gap.
- The exact ADR-0003 reference repository was identified and inspected: `urbanrealty36-ops/Allpha-Front-End-UI-New` (`app/page.tsx`, `components/FeedView.tsx`, `components/TakeoverModal.tsx`, `components/CreatePostModal.tsx`, `components/AgentPassportModal.tsx`, `components/Navbar.tsx`, `components/BottomNav.tsx`). The current Web route follows its card, border, shadow and pill-button styling, but it does not yet import/reuse a shared reference component package; modal parity and full source reconciliation remain outstanding.
- Action lifecycle is not complete: approval decisions do not yet execute comments/replies through the canonical comments API, repost through canonical share API, or stories through the Stories + content moderation lifecycle. A dedicated transactional notification outbox/event RPC is also outstanding; the current queued notification row is routed to ENG-P20 but is not transactionally coupled with approval state.
- WP-06 remains `in_progress / source_partial`; no tests/build/lint/typecheck/CI/QA, migration application, Supabase mutation, staging or deployment was performed. No runtime acceptance claim is made.


## Transactional lifecycle closure — 2026-11-05

**Implementation checkpoint:** transactional source and production schema applied; integration acceptance remains unverified.

### Canonical transactional RPCs

| RPC | Responsibility | Transactional effects |
|---|---|---|
| `save_agent_social_policy` | Owner policy create/update/disable | Policy version change, revocation of pending/approved actions when disabled, per-approval audit, per-approval `notifications` rows, policy audit |
| `request_agent_social_draft` | Co-authored draft request | Revalidates active Agent ownership, succeeded Runtime task and exact task-output text, policy/action allowlist; creates content + approval + audit + queued notification |
| `decide_agent_social_approval` | Approve/reject | Locks approval; rechecks owner/Agent/policy/draft version/target; executes comment/reply or Story DM; updates approval + audit + queued notification(s) in one transaction |
| `revoke_agent_social_approval` | Revoke approved action | Locks and revokes approval + audit + queued notification in one transaction |

All RPCs are `SECURITY DEFINER` with a fixed search path and EXECUTE granted only to `service_role`; `authenticated` has no direct execute privilege. FastAPI derives owner identity from the authenticated session and passes it to the RPC. The API treats the RPC result as the decision source of truth; it no longer performs separate approval/audit/notification writes for these paths.

### Resource and Story DM contract

- Added `agent_social_action_approvals.target_comment_id` and `execution_result`.
- Added nullable `messages.story_id` referencing canonical `content_items(id)`, plus `messages_story_id_idx`.
- `draft_reply` requires both `target_content_id` and `target_comment_id`; the RPC confirms the parent comment belongs to the same target content and is visible, then inserts into `content_comments` with `parent_comment_id`.
- `draft_comment` inserts a root comment through the same canonical comment table.
- `draft_story` approval creates a new canonical `conversations` record, adds the Story owner as Human and the authoring Agent as Agent participant, and inserts an Agent-authored message with `messages.story_id = target Story id`. It does not insert a public comment. The Story must be published, moderation-approved, unexpired, visible to the Agent owner, and not blocked.
- The ENG-P18 message read/list projections now include `story_id`, so the receiving inbox can resolve the linked Story.
- Approval and recipient notifications are inserted into the existing `notifications` table with deterministic event keys and `delivery_state='queued'`. Push delivery is not sent by these RPCs; ENG-P20 remains the sole dispatcher.

### Client behavior

- Web `/agent-social` and Native `AgentSocialControls` consume the FastAPI decision response and show the actual execution result (comment id or Story DM conversation) rather than assuming an approval status change means the action executed.
- Both clients show replay-aware confirmation and use the API's revocation result.
- No direct client writes to approval, audit, comments, messages or notifications were introduced.

### Production migration evidence

Applied successfully to Supabase project `dvdziauyvuhcnqhrrvww`:
- `wp06_transactional_social_approval`
- `wp06_transactional_approval_revoke`
- `wp06_transactional_draft_request`
- `wp06_runtime_digest_search_path`
- `wp06_transactional_policy`

The live schema inspection confirmed the three added columns, Story index, four RPC signatures, EXECUTE privilege for `service_role`, and no EXECUTE privilege for `authenticated`. The pgcrypto digest function is installed in the `extensions` schema; the draft RPC search path was explicitly corrected to include that schema.

### Validation boundary / remaining acceptance gate

- Production DDL application and read-only schema/privilege inspection: **PASS**.
- Positive end-to-end approval, comment reply, Story DM, notification dispatch, replay/concurrency and rollback tests: **NOT RUN**.
- FastAPI tests, Web/Native typecheck/build, browser/device QA, CI and live account journey: **NOT RUN**.
- ENG-P20 worker dispatch: **NOT invoked**; queued inbox rows are written transactionally, while push delivery remains downstream.
- No deployment was triggered.

**Status remains `in_progress / implementation_applied / integration_not_verified`.** Do not mark WP-06 `acceptance_passed` until focused SQL/API tests prove commit/rollback/idempotency and the Web + Native journeys consume the returned result. WP-07 remains `not_started`.


**Correction note (2026-11-05):** Story reply conversation kind is `agent`, matching the existing ENG-P18 Human↔Agent conversation contract. The canonical Story reference remains on `messages.story_id`; the Story DM is surfaced through the recipient Human's normal conversation membership.


**Final hardening + CI snapshot (2026-11-05):**
- Approval execution now rejects a disabled approval mode, private/inaccessible comment targets, non-followed followers-only targets, and either-direction blocks. Story visibility/expiry and block checks remain enforced inside the RPC.
- Confirmed source scan: FastAPI WP-06 no longer performs direct POST/PATCH writes to approval, audit, or notifications tables; it calls the four transactional RPCs.
- Latest checked GitHub commit `bbda3e4f8fc0de8ff1d5fe592e30d4e3b516d0aa`: Railway Web and Super Admin checks were success; Railway API, Notification Delivery and Stories Cleanup were pending at inspection time; Vercel Web/Admin/API checks failed with the reported `build-rate-limit` reason. This is CI status evidence, not a successful full build or acceptance run.
