# WP-02 / ENG-P04 Acceptance Evidence Register — 2026-10-27

## Decision

**Both phases remain IN_PROGRESS / NOT ACCEPTED.** This register records source inspection and read-only live Supabase catalog evidence. It is not an acceptance sign-off. No tests, smoke scripts, typecheck, build, staging, device journey, deployment, write transaction, or migration was executed/applied for this review.

## Canonical scope and source evidence

Repository: `urbanrealty36-ops/Allpha-AI-Aplikasi`, default branch `main`.
Canonical plan: `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md`.
Operating gate: `AGENTS.md` requires the complete Master PRD, phase dependencies, existing source/schema, security/privacy contracts, and explicit evidence before advancing a phase.

### WP-02 — shared shell, identity, navigation and profile parity

Read-only source inventory reviewed:
- Web shared navigation: `apps/web/components/reference-ui/ReferenceNavigation.tsx`.
- Web account/settings/social/privacy route: `apps/web/app/account/page.tsx`.
- Web profile route: `apps/web/app/profile/page.tsx`.
- Web Search / discovery: `apps/web/app/search/page.tsx`.
- Web inbox and notifications: `apps/web/app/messages/page.tsx`, `apps/web/app/notifications/page.tsx`.
- Native stack, deep links, shared tab adapters and authenticated identity journey: `apps/client/App.tsx`.
- Source-contract assertions: `apps/web/scripts/smoke-test.mjs`.

Source-level evidence found:
1. Native deep-link route names exist for Profile, Account, Agents, Feed, Reels, Stories, Search, Messages, Notifications and Communities. The authenticated Native stack adapts these routes to Profile tabs; Account carries profile/settings/social/consents tab parameters.
2. Web Account persists preferences through authenticated FastAPI `/v1/me/settings`, rather than directly writing the table from the client. The Native settings flow also uses the API.
3. Search uses the canonical social graph and username discovery endpoints; pending private-profile follow requests are distinguished from active follows.
4. Messages and Notifications now invalidate prior-account state and sequence asynchronous requests across auth changes. Source assertions were added, but have not been executed.
5. Profile adapter intentionally does not invent takeover state, social counts, or verification status when canonical data is unavailable.

WP-02 remains open because source inspection is not proof of full reference UI parity, successful compilation, responsive rendering, deep-link behavior on devices, real-time inbox behavior, or end-to-end route completion. The fixed plan already records unresolved story viewer / reference-menu interactions and broader source-to-route and CSS/assets reconciliation. Those must be reconciled against the reference UI rather than simulated.

### ENG-P04 — social graph, privacy and database privileges

Read-only live Supabase project inspected through the connected AllphaAiAplikasi-db project:
- Project ref: `dvdziauyvuhcnqhrrvww`.
- Live migration history includes migrations through `20261021113639_eng_p22_theme_builder_registry`.
- The source migration `20261027180000_eng_p03_user_settings_least_privilege_grants.sql` is **not present** in the live migration history.
- RLS is enabled on `user_settings`, `profiles`, `social_edges`, `conversation_participants`, `conversations`, `messages`, and `notifications`; `relforcerowsecurity` is false on these tables.
- Existing `user_settings` policies scope SELECT/INSERT/UPDATE rows to `auth.uid()`. The inspected profile policy allows authenticated SELECT for public profiles or the caller's own profile; social-edge policies are actor/participant scoped; message and conversation-participant SELECT policies call `eng_p18_can_read_conversation(conversation_id)`.
- **Blocking live grant finding:** read-only `has_table_privilege` reports `anon` and `authenticated` can SELECT, INSERT, UPDATE, DELETE and TRUNCATE `public.user_settings`. Catalog column grants also list INSERT/SELECT/UPDATE/REFERENCES on every `user_settings` column for `anon` and `authenticated`. RLS is not a substitute for revoking excess SQL privileges.
- The version-controlled forward migration source revokes table and column privileges from `public`, `anon`, and `authenticated`, then grants authenticated SELECT plus narrowly scoped INSERT/UPDATE columns. It has not been applied, and no production DDL was performed during this review.

This finding is a release blocker for ENG-P04. Do not claim least-privilege grants are effective until the approved migration process applies the reviewed migration and read-only catalog queries confirm the expected grants. Do not apply the migration ad hoc as part of this evidence-only review.

## Verification boundaries

- Read-only: repository source retrieval, Supabase migration history, table/RLS catalog, policy catalog, table and column privilege catalog.
- Not performed: authenticated two-user allow/deny tests; API integration tests; RLS behavior under end-user JWTs; Realtime cross-user isolation; browser/device QA; build/typecheck/test/smoke execution; production migration or deployment.
- Source regression tests and smoke assertions are contracts only until an authorized validation window permits execution.
- No Agent Identity, Runtime/Skills, Super Admin or Spatial/GLB phase is promoted by this evidence register.

## Required exit evidence

### WP-02
- Complete reference-to-target route/component/asset/CSS manifest with checksums and explicit disposition for every gap.
- Approved validation window: Web typecheck/build/smoke and responsive screenshots at 360/390/820/1440 px, plus Native typecheck and deep-link/device acceptance. This register does not authorize those checks.
- Evidence for identity switching, session expiry, search/follow/request/cancel, profile visibility, notifications and Messages/Reatime states, including error/empty/loading paths.
- Resolve or explicitly defer with owner/ADR the story viewer and reference-menu gaps; no fake success states.

### ENG-P04
- Review and approve the existing least-privilege migration.
- Apply only through the authorized migration process; verify migration history and exact table/column grants afterward.
- Execute authorized two-user privacy checks for private profiles, discoverability preferences, follow requests, block/mute, inactive accounts, shared links/comments, inbox/notifications and realtime membership.
- Capture API/RLS allow/deny evidence and confirm no cross-user data leakage.

## Phase order

Keep WP-02 and ENG-P04 `IN_PROGRESS` until the above evidence is reviewed and accepted. Only then begin ENG-P05 — Agent Identity. Runtime/Skills, Super Admin, and Spatial/GLB remain downstream of their canonical engine owners and dependencies.


## Route parity inventory (source-level, not device acceptance)

The reference shell's current `routeForTab` mapping in `apps/web/components/reference-ui/ReferenceNavigation.tsx` was compared with the Native stack and deep-link config in `apps/client/App.tsx`. This inventory is intentionally explicit about gaps rather than routing missing features to fake placeholders.

| Reference shell tab / journey | Web canonical route | Native deep link / stack | Source disposition |
|---|---|---|---|
| FEED | `/feed` | `allpha://feed` → Feed tab | Route name exists; content/scroll/engagement parity still needs device evidence |
| EXPLORE | `/search` | `allpha://search` → Discovery tab | Search/discovery API wired; device and visual parity not verified |
| CREATE | `/create` | None in Native linking/stack | Open parity gap; do not simulate successful publishing |
| LIVESTAGE | `/live` | None in Native linking/stack | Open parity gap; no placeholder route added |
| WORLD3D | `/spatial/navigation` | None in Native linking/stack | Open parity gap; downstream Spatial owner/dependencies apply |
| MESSAGES | `/messages` | `allpha://messages` → Messages tab | API-backed inbox and auth/session guards; realtime/device behavior unverified |
| REELS | `/reels` | `allpha://reels` → Reels tab | Route name exists; playback/gesture parity needs device evidence |
| SKILLS_CREDITS | `/skill-challenges` | No dedicated deep-link route; Native challenge UI is nested under existing profile/Agent journey | Direct-route parity gap; do not invent a separate engine |
| MARKETPLACE | `/marketplace` | None in Native linking/stack | Open parity gap; Marketplace owner/dependencies apply |
| PROFILE | `/profile` | `allpha://profile` → Profile tab | Route name exists; social metrics/verification/takeover intentionally not fabricated |
| POST_DETAIL | `/feed?content=…` | `allpha://feed` has no source-level query-to-content mapping in linking config | Deep-link parameter parity gap; do not claim direct post detail parity |
| TAKEOVER_CONTROL | `/agents` | `allpha://agents` → Agent tab | Route name exists; runtime state must remain canonical/API-derived |
| ASK_AI_VIEW | `/ask-ai` | None in Native linking/stack | Open parity gap; no client-only AI response path added |
| FILM_AI | `/ai-cinema` | None in Native linking/stack | Open parity gap |
| Stories | `/stories` is treated as Feed by shared navigation's active-tab resolver; source also has story-viewer modal behavior | `allpha://stories` → Stories tab | Behavior mismatch remains: direct story viewer / selected-story deep-link contract needs owner/API decision |
| Notifications | `/notifications` | `allpha://notifications` → Notifications tab | Route name exists; push/device delivery and realtime state not verified |
| Communities | `/communities` | `allpha://communities` → Communities tab | Route name exists; device journey and visual parity not verified |
| Account / settings / social / consent | `/account?tab=profile|settings|social|consents` | `allpha://account` with tab parameter | Source mapping exists; authenticated deep-link behavior still needs device evidence |

This inventory demonstrates that **WP-02's source-level route parity is not complete**. The next implementation slice should not add fake routes or duplicate domain engines. Route gaps that belong to later canonical owners (Spatial, Marketplace, AI Cinema, Agent Runtime/Skills) must be linked to their owner phases and should remain blocked until those owners' contracts are ready. For WP-02-owned shell gaps, the owner must decide/implement an explicit deep-link contract for post detail and story selection without bypassing canonical API authorization.

## Read-only Supabase evidence detail

The live SQL catalog checks were read-only and inspected:
- `pg_class.relrowsecurity` / `relforcerowsecurity` for the reviewed tables;
- `pg_policies` for row policies;
- `has_table_privilege(role, 'public.user_settings', privilege)` for SELECT/INSERT/UPDATE/DELETE/TRUNCATE;
- `information_schema.column_privileges` for `user_settings` column grants;
- live migration history for presence/absence of `20261027180000_eng_p03_user_settings_least_privilege_grants`.

The results are recorded above. These queries do not exercise end-user JWT policy evaluation, so cross-user isolation remains unverified even where a policy expression appears correctly scoped.


## Follow-up source contract

- Added a source-level smoke assertion for the exact user_settings privilege migration contract: broad table revoke, column revoke, authenticated SELECT, and restricted INSERT/UPDATE column lists. Commit: `37f3822c7d64bdb6e7659b59bb54848e71eb856b`.
- The smoke script was **not run**. This assertion detects source drift only; it cannot prove the migration has run or that live grants are corrected.


## Reference/target source manifest (read-only inventory)

Blob SHA values below are the GitHub file blob SHAs returned by the repository connector; byte counts are UTF-8 source lengths from the retrieved content. They identify exactly which source was inspected, not visual equivalence.

| Role | Path | Blob SHA | Bytes | Review result |
|---|---|---|---:|---|
| Reference | `app/page.tsx` | `0bddfa37d8dbc307d0362b742b66ee644f9dfba0` | 27,391 | Reference SPA composition; contains demo/store state and modal/tab behavior requiring API-backed adapter parity, not direct promotion |
| Reference | `app/globals.css` | `5a7873abc0ed6501cce9c86073350bfc602cfcb2` | 49 | Reference base stylesheet |
| Reference | `components/Navbar.tsx` | `fab9a740d3a7a8d81e7219be27f01b9d67ca8261` | 7,826 | Header/navigation visual source |
| Reference | `components/BottomNav.tsx` | `c2841cf7048bd2130f8634435d683523e04325d6` | 6,357 | Mobile navigation visual source |
| Reference | `components/ProfileView.tsx` | `c55452a78cee9f1e33f2480bea39049f24882348` | 74,976 | Profile visual/interaction source |
| Reference | `components/ExploreView.tsx` | `9e1f3a9f7c43ee4ed0c250842d6c93e0200e5701` | 45,784 | Explore/Search visual/interaction source |
| Reference | `components/MessagesView.tsx` | `20685f8eb9e5f16df8f1163bcd9198f23cc25f56` | 8,096 | Inbox visual/interaction source |
| Target | `apps/web/app/globals.css` | `1d22919ddf820336cbe4d17064ca7d97e367032b` | 21,310 | Target stylesheet is substantially larger; route-scoped cascade/asset parity remains open |
| Target | `apps/web/components/reference-ui/ReferenceNavigation.tsx` | `d499ce9d86a45a3f23c0f2018172522fccf8ec81` | 6,097 | Shared navigation adapter and route map |
| Target | `apps/web/components/reference-ui/ExploreView.tsx` | `cfe9a582b35d3d1398bc65abf298c8834b6b7f32` | 48,574 | API-backed Explore adapter; not visually accepted |
| Target | `apps/web/components/reference-ui/MessagesView.tsx` | `7074ec42cf02c670781d353c02235a9317204a7e` | 8,042 | API-backed inbox adapter; not visually/device accepted |
| Target | `apps/web/components/reference-ui/ProfileView.tsx` | `479a40e777357bd530ed879d58f6cfd9102f3901` | 78,066 | Profile adapter; intentionally suppresses unavailable metrics/runtime claims |
| Target | `apps/web/app/feed/page.tsx` | `85fb59c745929dbf8e513aef424018f5f5d39808` | 29,381 | API-backed Feed route; story click-through still needs canonical viewer contract |
| Target | `apps/web/app/search/page.tsx` | `75c28213273646537d8e43b287a8de563e54c252` | 20,322 | API-backed search/discovery and session/request sequencing |
| Target | `apps/web/app/messages/page.tsx` | `0d0349a0762b613028bc33c3c29a05457cf9f580` | 10,877 | Auth-scoped inbox adapter and request sequencing |
| Target | `apps/web/app/notifications/page.tsx` | `5a3351870eea29d4ac2d62854d4675487c8039e8` | 12,515 | Auth-scoped notification/preferences adapter |
| Target | `apps/web/app/profile/page.tsx` | `3d590ade12c16b43ff36fac434401ae57213c668` | 15,949 | Profile adapter; unavailable counts/takeover state are not fabricated |
| Target | `apps/web/app/account/page.tsx` | `d977cf0cc45e84ca3c295d47b7b0fec95b742e98` | 36,071 | Account/settings/social/consent route and query-tab mapping |

The manifest is now source-checksum traceable for the principal WP-02 journeys, but it is not yet the complete public-asset/font/icon/image manifest and does not resolve dynamic CSS, responsive breakpoints, screenshot diff, animation/gesture, accessibility, or interaction acceptance. Those require a permitted validation window; no test/build or screenshot was performed here.
