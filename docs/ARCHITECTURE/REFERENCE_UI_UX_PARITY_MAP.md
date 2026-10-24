# Reference UI/UX Parity — Source-to-Canonical Mapping

**Status:** Audit baseline; implementation remains in progress  
**Decision:** [ADR-0003](../ADR/ADR-0003-reference-ui-ux-parity-pwa-web.md)  
**Reference source:** https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New  
**Canonical source:** this monorepo, branch `main`

## Guardrails

- Preserve the reference's visible design, component hierarchy, navigation affordances, interaction patterns, and journeys; do not copy its local-data assumptions as business truth.
- Canonical journey: Splash → Human Register/Login → AI Agent Identity onboarding/register → Feed home.
- Universe 3D is a navigable hub, not the default home.
- Web and Expo Native must offer equivalent domain capabilities and journey outcomes. Platform-specific implementation is acceptable where required by React/React Native.
- Business operations must go through typed/versioned FastAPI contracts and canonical domain engines; Supabase remains the canonical data store. Supabase Auth/session handling is allowed where designed. No client-side business writes, direct client LLM SDK calls, mock data, or simulated success.
- Missing endpoints/engines/schema must be implemented in their existing owner ENG phase, not hidden behind UI-only local state. Do not advance a phase based on a visual shell alone.

## Initial source inventory

The reference app is a single Next.js application whose root `app/page.tsx` owns tab/view state and composes the following domain views/components. The reference's UI is a design/interaction contract, not the canonical architecture.

| Reference view/component | Canonical Web target | Canonical Native target | Domain/API ownership to verify |
|---|---|---|---|
| `AuthOnboardingFlow` | Auth/onboarding route and shared shell | `Auth` / onboarding screens in `apps/client/App.tsx` | ENG-P02/ENG-P03; Supabase Auth plus FastAPI identity/profile provisioning |
| `AgentIdentityModal` | Agent identity onboarding route/screen | Agent onboarding screen/flow | Existing Agent identity phase; canonical `/v1/agents` contracts |
| `FeedView` | Web Feed home after onboarding | Feed screen in Native app | Social/content phase; Native already references `/v1/feed`, `/v1/content`, reactions/comments and feed preferences; Web currently only exposes identity/settings/social graph in `app/page.tsx` |
| `ExploreView` | Explore/search/trends route | Explore/search screen | Native references `/v1/search`, `/v1/recommendations`, `/v1/trends`; Web wiring is not present in its current home page |
| `ReelsView` | Reels route | Reels screen | Native references `/v1/reels`; verify media delivery, moderation and playback contracts |
| `MessagesView` | Messages/conversations route | Messages screen | Native references `/v1/messages/conversations`; verify unread/read and send contracts |
| Stories / create / post detail | Stories, composer and detail routes | Native story/composer/detail screens | Native references `/v1/stories`, `/v1/content`; preserve server moderation/publish states |
| `ProfileView` | Profile route | Existing Profile screen | ENG-P03; current Web uses `/v1/me`, `/v1/me/profile`, `/v1/me/settings` |
| `TakeoverControlView` / takeover modal | Agent takeover/permissions route | Agent-control screen | Existing Agent runtime/authorization phase; verify consent, permission scopes and audit trail |
| Skills / challenges | Skills/challenges routes | Native skills/challenges screens | Native references `/v1/skill-catalog`, `/v1/skill-challenges/*`; canonical skill/evaluation/reward owners |
| AI Cinema / film studio | AI Cinema route | Native equivalent route/screen | Existing creator/economy phases; verify media job lifecycle, entitlement and canonical ledger before wiring |
| Marketplace | Marketplace route | Native equivalent route/screen | Existing marketplace/commerce owner phase; do not invent inventory, price, payment or order status |
| Allpha Hub / Live Stage | Hub and live experience routes | Native live experience screens | Existing community/live/media phases; verify session lifecycle and authorization |
| `Universe3DHubView` / `ThreeWorldView` | 3D hub route, secondary to Feed | Existing spatial navigation/theme/renderer screens | ENG-P22–P24 and later spatial phases; use canonical scene/asset manifests and publication gates |
| Credits / skills economy | Wallet/ledger route | Native wallet/ledger route | ENG-P09 economy/ledger owner; display canonical balances only, never client-generated rewards |
| `BottomNav` / `Navbar` | Responsive navigation shell | Native navigation shell | Navigation parity; active state must match actual route and auth state |

## Confirmed current-state gaps from source inspection

1. `apps/web/app/page.tsx` is currently an identity/settings/social-graph/consent experience. Its observed API calls are `/v1/me`, `/v1/me/settings`, `/v1/me/consents`, `/v1/me/social-graph`, `/v1/me/profile`, and `/v1/me/deactivation-request`. It is not yet the reference Feed-first multi-domain UI.
2. `apps/client/App.tsx` is a much broader authenticated client and contains source references to feed, content, stories, reels, search, trends, recommendations, messages, notifications, Agent identity/runtime, skills/challenges, communities/workspaces and spatial screens. This is source evidence of client wiring only; it does not prove every endpoint is implemented or live.
3. Reference `app/page.tsx`, `FeedView.tsx`, `BottomNav.tsx`, `AuthOnboardingFlow.tsx`, `AgentIdentityModal.tsx`, and `ExploreView.tsx` were fetched from the reference repository. The reference is single-app/client-state oriented and includes local/sample state; those state patterns must not be ported as business truth.
4. API module root is `apps/api/allpha_api` per repository README, not `apps/api/main.py`. Endpoint-to-router/service/repository/migration verification remains an explicit implementation task; endpoint literals in clients alone are insufficient evidence.
5. Native app route type at the top of `apps/client/App.tsx` currently declares only `Welcome`, `Auth`, and `Profile` for the root stack type, while the same file imports additional feature screens. Inspect the full navigation implementation before changing route types; do not infer missing routes from imports alone.

## Implementation order (existing phase owners only)

1. Map every reference view and interaction to a canonical route/screen, then trace each user action to FastAPI router → auth/policy → domain service/engine → repository → Supabase schema/RLS/migration.
2. Close the identity journey and route guards before rendering Feed as the authenticated home (ENG-P02/ENG-P03 and existing onboarding/Agent identity owner).
3. Implement the Feed-first shared navigation and port reference visual hierarchy without copying local sample data; wire Web to the same canonical API contracts already consumed by Native where appropriate.
4. Port remaining views by their existing domain owners: social/content, messaging/live, skills/runtime, economy/creator commerce, and spatial/asset governance.
5. Add route-level loading, empty, error, permission-denied and retry states; preserve moderation and entitlement gates.
6. Run source/unit/contract/typecheck/lint/build checks during implementation. Consolidated isolated non-production integration and cross-client journey acceptance remains at ENG-P37 as defined by the fixed phase plan.

## Coverage and validation

- Web: **CHANGE** — current home is not the reference Feed-first UI.
- API/DB: **AUDIT + targeted CHANGE per owning phase** — source trace is required before each workflow is wired; no blanket schema migration is justified by UI parity alone.
- Native Android/iOS: **CHANGE/INTEGRATE** — preserve current API-backed capabilities while aligning screen journeys and visual hierarchy.
- Super Admin: **NOT AFFECTED by end-user UI parity** — remains a separate operator surface; only change if an owned domain's existing admin workflow is required.
- Tests: no new tests are claimed by this audit document. Current CI status is not asserted here. No production migration or business-data write was performed.
- Phase status: keep affected phases `in_progress` until their own acceptance evidence exists; do not mark full UI/UX refactoring complete from this mapping.


## Focused parity pass — Shell, Feed, Create, Stories, Reels (2026-10-24)

| Surface | Web implementation observed | Native implementation observed | Current parity result / gap |
|---|---|---|---|
| Authenticated journey / shell | `/start` checks session and canonical `GET /v1/agents`; Feed links to Create, Stories and Reels. | `Navigator` checks the same Agent identity contract and passes an initial `agents` or `feed` tab to the authenticated Profile screen. | Journey gate exists in source. Web routes are separate pages while Native features are sections in the Profile screen; a common responsive route/navigation shell matching reference `BottomNav` is not yet complete. |
| Feed | `/feed` uses authenticated `/v1/feed`, preferences, cursor pagination and server-backed reactions/comments/saves/reports/shares. Links to `/create`, `/stories`, `/reels`. | Native has Feed/content data types and server-backed social actions inside the authenticated Profile screen. | API-backed feature families exist in both source trees; parity is not acceptance-passed until route-level behavior, empty/error/loading states, pagination and interaction results are exercised on Web and device. |
| Create | `/create` posts a draft to `POST /v1/content`, optionally uploads media to `/v1/content/{id}/media`, then calls `/publish`; publication is moderation-gated. Exact media MIME types and backend-aligned size limits are validated before draft creation. | Native exposes content draft creation, media selection and content API contracts inside Profile. | Native and Web expose different UI steps; verify equivalent media validation, recoverable draft state, publish/moderation feedback, and idempotent retry behavior. No direct client database writes. |
| Stories | `/stories` uses `GET /v1/stories/mine`, `GET /v1/stories`, `POST /v1/stories`, shared content media upload/publish and `DELETE /v1/stories/{id}`. | Native has a Stories/Moments section with active and own story lists, media picker, submit-to-moderation and reload actions. | Same domain lifecycle is referenced. Still verify exact TTL/visibility handling, failed-upload recovery, expiry behavior, and actual API authorization/integration. |
| Reels | `/reels` uses `GET /v1/reels`, media preview playback, and canonical Feed reaction/share endpoints. | Native includes a Reels list, like/share actions and pagination in the authenticated screen. | Core capabilities are represented; verify media compatibility/playback, pagination and share fallback on Android/iOS. |
| Shared reference shell | Reference `BottomNav` / `Navbar` is the interaction contract, not a source of business truth. | Native uses one Profile screen with internal tab state and stack navigation for Welcome/Auth/Profile. | **Open gap:** consistent active navigation state, selected-tab deep linking, and reference component hierarchy are not yet proven equivalent. Do not mark the parity work complete from source inspection alone. |

Validation added in commit `85eb613` extends `apps/web/scripts/smoke-test.mjs` to assert the Feed/Create/Stories/Reels API and navigation contracts, including that no mocked business collections are used. Media preflight fix in `bd65961` rejects unsupported MIME types and files over backend limits before creating a draft. The source assertions have been committed but have not yet been executed in this session; Vercel build completion is not equivalent to running this smoke-test script.


## Checkpoint A closure inventory — source tree observed 2026-10-24

Reference tree: `5184f44e9f6c4e641cbe37e9f743583cf40d785e` (branch `main`). Canonical tree observed before this documentation update: `5b00bba180ebb6a2249870fbf9acf660d21af639`. The source tree has 73 blobs across 90 tree entries; all 25 top-level `components/*.tsx` entries are represented below. This closes the *inventory* portion of Checkpoint A; it does not mean components are runtime-wired or visually accepted.

### 25 component source → canonical target → route map

| Reference component | Canonical copied source | Existing route / route gap | Target file status | Source blob SHA |
|---|---|---|---|---|
| `AgentGoalsTasksModal.tsx` | `apps/web/components/reference-ui/AgentGoalsTasksModal.tsx` | `/agents/[agentId]/studio` (candidate; action/route integration pending) | present; copy exists | `8f7990a47b5bdb4c39286e5ab12b169fbfb2bdc3` |
| `AgentIdentityModal.tsx` | `apps/web/components/reference-ui/AgentIdentityModal.tsx` | `/agents` (existing; onboarding route wiring pending) | present; copy exists | `812625ed02ffaec4ffec1ff0661eae05447557fd` |
| `AiCinemaView.tsx` | `apps/web/components/reference-ui/AiCinemaView.tsx` | NEW route required (suggest `/cinema`; do not implement route until component-port checkpoint) | present; copy exists | `8f0978d57f3b5d679820a0d8c8fdc8a183cf9dae` |
| `AllphaHubView.tsx` | `apps/web/components/reference-ui/AllphaHubView.tsx` | `/communities` (existing route; visual composition parity pending) | present; copy exists | `9ce176b8e7fe1cd7a6833a89477aebe24594e6d0` |
| `AskAiModal.tsx` | `apps/web/components/reference-ui/AskAiModal.tsx` | Existing Agent workspace route candidate (`/agents/[agentId]/studio`); no dedicated Ask AI route confirmed | present; copy exists | `79dfe76d2bd727c2a40e9b442b0fb82aefd7d091` |
| `AskAiView.tsx` | `apps/web/components/reference-ui/AskAiView.tsx` | Existing Agent workspace route candidate (`/agents/[agentId]/studio`); no dedicated Ask AI route confirmed | present; copy exists | `c040e2fd89e9cb20075bb198286811265ca9dacc` |
| `AuthOnboardingFlow.tsx` | `apps/web/components/reference-ui/AuthOnboardingFlow.tsx` | `/` and `/start` identity journey; preserve canonical Supabase Auth | present; copy exists | `0ae993ee0540352a9e2994dab7cd87a3ec6904f3` |
| `BottomNav.tsx` | `apps/web/components/reference-ui/BottomNav.tsx` | Shared shell on authenticated routes; existing target `ReferenceNavigation.tsx` partial | present; copy exists | `40d64c49fe279710c702708d1e5dbfc30c9c9618` |
| `CreatePostModal.tsx` | `apps/web/components/reference-ui/CreatePostModal.tsx` | `/create` (existing route; source modal can be reused without demo state) | present; copy exists | `3d1c326ab9ec7752f47ec9a3fe788db23bc55750` |
| `ExploreView.tsx` | `apps/web/components/reference-ui/ExploreView.tsx` | `/search` (existing route); Explore-specific view may need a new route | present; copy exists | `1d71c457bfec41810db0f870beb42d790995cd8e` |
| `FeedView.tsx` | `apps/web/components/reference-ui/FeedView.tsx` | `/feed` (existing route) | present; copy exists | `0df4fe886e63d2c89e64207a38cab1acd2b14aa1` |
| `GenerateModal.tsx` | `apps/web/components/reference-ui/GenerateModal.tsx` | `/content-studio` (existing route; no provider/business wiring in this checkpoint) | present; copy exists | `b694cbb8135f581aa064cf499c29963291c19c3d` |
| `LiveExperienceStage.tsx` | `apps/web/components/reference-ui/LiveExperienceStage.tsx` | NEW route required (suggest `/live`; no canonical route found) | present; copy exists | `15583edb11792fc370b88e88b3ea59f5072fa5ae` |
| `MarketplaceView.tsx` | `apps/web/components/reference-ui/MarketplaceView.tsx` | NEW route required (suggest `/marketplace`; no canonical route found) | present; copy exists | `90f2a4b76adf00cf46fe5e06c61cd2ec43be46f1` |
| `MessagesView.tsx` | `apps/web/components/reference-ui/MessagesView.tsx` | `/messages` (existing route) | present; copy exists | `24153bb9fd37669ebdde383fb4e940e994d0936e` |
| `Navbar.tsx` | `apps/web/components/reference-ui/Navbar.tsx` | Shared shell; existing target `ReferenceNavigation.tsx` partial | present; copy exists | `c566d22fe5310adcc96965e65c6764d55512819f` |
| `PostDetailView.tsx` | `apps/web/components/reference-ui/PostDetailView.tsx` | NEW route required (suggest `/posts/[postId]`; no canonical route found) | present; copy exists | `57143b041f446454f66d38b8d46be94a34774fd5` |
| `ProfileView.tsx` | `apps/web/components/reference-ui/ProfileView.tsx` | `/agents/passport/[handle]` only for Agent passport; human profile route needs verification/new route | present; copy exists | `92a01fc2be7bd0e5108b9e3715afff114de72d98` |
| `ReelsView.tsx` | `apps/web/components/reference-ui/ReelsView.tsx` | `/reels` (existing route) | present; copy exists | `9708f92b32654cb0ddce9d023461864a12339ac2` |
| `SkillsChallengeHub.tsx` | `apps/web/components/reference-ui/SkillsChallengeHub.tsx` | `/skill-challenges` (existing route) | present; copy exists | `a7868c00a333d918bca176ae355b6c8a683ce626` |
| `TakeoverControlView.tsx` | `apps/web/components/reference-ui/TakeoverControlView.tsx` | `/agents/[agentId]/studio` (candidate; canonical policy actions must not be wired in UI-only checkpoint) | present; copy exists | `9b261d3c894119bf1eb3ea929f6ddbfbcb8db236` |
| `TakeoverModal.tsx` | `apps/web/components/reference-ui/TakeoverModal.tsx` | `/agents/[agentId]/studio` (candidate; confirmation component only) | present; copy exists | `4797dfca29205e9ee88d88c3e601862b12ef7944` |
| `ThreeWorldView.tsx` | `apps/web/components/reference-ui/ThreeWorldView.tsx` | `/spatial/[sceneKey]` (existing route; component wiring pending) | present; copy exists | `74da25aa6790bc7a3d340423e08ddcd533e01f38` |
| `Universe3DExperience.tsx` | `apps/web/components/reference-ui/Universe3DExperience.tsx` | `/spatial/navigation` (existing route; component wiring pending) | present; copy exists | `5ac27375f9629bd9b06d59c0a29c52da63e0b2f9` |
| `Universe3DHubView.tsx` | `apps/web/components/reference-ui/Universe3DHubView.tsx` | `/spatial/navigation` (existing route; secondary hub, never Feed home) | present; copy exists | `4792f79cf9300748a7c74749fc4a330832718cd9` |

### Supporting files and ownership boundaries

| Source file/group | Purpose | Canonical handling |
|---|---|---|
| `app/page.tsx` | Reference root view/tab orchestrator | Preserved in reference archive only; uses demo/local state and must not replace canonical `apps/web/app/page.tsx` |
| `app/layout.tsx` | Reference root metadata, viewport, document shell | Archive only; canonical root layout remains authoritative |
| `app/globals.css` | Source CSS entry point | Current source is only 49 bytes and imports Tailwind + `tw-animate-css`; full design styles are mostly component-level/other dependency styles, so inspect component class usage and source package dependencies rather than assuming this file contains the full design system |
| `hooks/use-mobile.ts` | Responsive breakpoint hook | Copied to `apps/web/hooks/use-mobile.ts`; review imports and actual use before wiring |
| `hooks/usePWAInstall.ts` | Install prompt hook | Copied to `apps/web/hooks/usePWAInstall.ts`; source-only until route/shell wiring |
| `lib/store.ts` | Reference UI's initial data and local state store | Archive-only; contains sample/initial data and cannot be used as production business truth |
| `lib/utils.ts` | Reference helper utilities | Archive-only until import/dependency compatibility is verified |
| `app/api/agent/interact/route.ts` | Reference Agent interaction route | Archive-only; canonical business logic remains in `apps/api` and must not be shadowed by a Next route |
| `package.json`, `next.config.ts`, `tsconfig.json`, lint/PostCSS config, env example | Reference app tooling | Archive-only; do not overwrite monorepo app configuration |
| `public/icon.svg`, `public/assets/aistudio/*` | Visual reference assets | Asset-by-asset reconciliation below; binary transfer gaps remain explicit |
| `.aistudio/artifacts/brain/**/.tempmediaStorage/*` | AI Studio generated temporary media | Source tree inventory only; these are temporary media artifacts and must not be copied into public runtime assets without explicit UI usage/path mapping |

### Reference binary assets — checksum/path reconciliation

Source inventory contains 19 files under `public/assets/aistudio/`. Matching exact target path status:

| Source asset | Bytes | Source blob SHA | Canonical target |
|---|---:|---|---|
| `ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE__1__3ae29f78.md` | 129536 | `ff7b7b14b1245da0d6e6510dea4f033d8099c1a9` | MISSING at canonical path |
| `Screenshot_20261015-164747_fd4f48e4.jpg` | 915577 | `4a2dee71322ee123ff7a835789e0e5820af3fda2` | present at same path |
| `Screenshot_20261020-224657_48336231.jpg` | 464766 | `53e9c361665384c8e66d9379468eeac5d18a0788` | present at same path |
| `Screenshot_20261022-214044_2d568e43.jpg` | 1105749 | `808ddbb761676c06e91ba6e092244511e1d1e899` | MISSING at canonical path |
| `Screenshot_20261022-220040_ce194f62.jpg` | 699468 | `dc1dbd4d93a89155e44dc0d0e499b3022684aabc` | present at same path |
| `Screenshot_20261023-174657_88e4a1c1.jpg` | 644676 | `d2383fd34b56cff879be3fd2291ab0662aae51e3` | present at same path |
| `Screenshot_20261023-182318_4e89cb4b.jpg` | 590774 | `4182881e0a3d78e7d1a757e2c2622fea98d3a151` | present at same path |
| `Screenshot_20261023-182405_d765b801.jpg` | 672454 | `0730fcf3e580a6c8a3bc10cc6aabfb4cd1d45010` | present at same path |
| `Screenshot_20261023-185525_22a42efd.jpg` | 1104144 | `8e58ed3ef6c1562c027ad45ff56f265e357e2d77` | MISSING at canonical path |
| `Screenshot_20261023-190053_0db052a1.jpg` | 586619 | `14e593bb3b4f465f386294f8250cf7c26ebf7d5d` | present at same path |
| `Screenshot_20261023-191515_c07d41e9.jpg` | 558343 | `2844a29f29371611e638158eae79a167560eafd1` | present at same path |
| `Screenshot_20261023-204929_f99e67e4.jpg` | 741976 | `b63fe9a95b0b1aceff9315731b0156ef53a2d161` | present at same path |
| `Screenshot_20261023-205615_1e35e812.jpg` | 685285 | `597c4ee0de2cc0ab7e114ef650f2d4a18916812d` | present at same path |
| `Screenshot_20261023-211448_393205d1.jpg` | 651621 | `422d339e4c9c48e2bac26c9bf435c93408fb58b3` | present at same path |
| `file_000000000124820cac0b31096f36996d_47c73336.png` | 2284057 | `12d6c93d1f47e22017355db24d5c5f9d650eac64` | MISSING at canonical path |
| `file_00000000560c820baca9cd747fc97471_b104badb.png` | 2070206 | `b0cbd91174768e7eb979f9920b85f637f7d920f4` | MISSING at canonical path |
| `file_000000008064820b8790f095225931fd_64393eeb.png` | 2092646 | `e89cac55c852fc19a76c53427fe79ba42426ef50` | MISSING at canonical path |
| `file_00000000d1c08207a6952642d1a26363_df39e383.png` | 2674422 | `7bcb5eb6a77de90eb449a8acfda0ddf7aeadcb66` | MISSING at canonical path |
| `file_00000000d5a08211bff1d1706016eb9d_2018bbd5.png` | 2663435 | `749060b67cf8d143fc360c6c45e7742b849c27ab` | MISSING at canonical path |

Additional temporary media under `.aistudio/artifacts/brain/**/.tempmediaStorage/` are inventoried in the source Git tree but are not public assets and have no confirmed runtime references. Do not bulk-copy them into `public/` merely because they exist.

### Route coverage and new route candidates

Canonical Web routes observed in `apps/web/app`: `/agents/[agentId]/studio, `/agents, `/agents/passport/[handle], `/communities, `/content-studio, `/create, `/feed, `/messages, `/notifications, `, `/reels, `/search, `/skill-challenges, `/spatial/[sceneKey], `/spatial/navigation, `/spatial/themes, `/start, `/stories, `/theme/[themeKey], `/workflows.

Route gaps discovered from source component inventory:
- AI Cinema: no dedicated `/cinema` route confirmed; candidate route only.
- Live Experience Stage: no dedicated `/live` route confirmed; candidate route only.
- Marketplace: no dedicated `/marketplace` route confirmed; candidate route only.
- Post Detail: no `/posts/[postId]` route confirmed; candidate route only.
- Human Profile: Agent passport route exists, but it is not automatically equivalent to a human profile route.
- Ask AI and Explore have component-level designs, but dedicated canonical routes are not confirmed by the current route tree.
These are route inventory findings, not authorization to implement new layouts in Checkpoints A/B.

### Runtime archive isolation audit

Observed `apps/web/tsconfig.json` excludes `reference-source/**` and `components/reference-ui/*.tsx`, but its glob does not explicitly exclude every `*.reference` file or `docs/reference-ui-source/**`. Existing `.reference` snapshots use a non-TypeScript extension and are not compiled as TS/TSX by default; source snapshots under `docs/` are outside `apps/web`. The archive under `apps/web/reference-source/` is outside Next's `app/` directory, but should remain excluded from TypeScript/lint inputs. Do not delete or rewrite existing snapshots; add explicit exclusions only if the build/lint configuration actually traverses them.

### Checkpoint A result

- **Inventory:** complete for the observed source tree and 25 top-level components.
- **Route mapping:** complete as existing-route vs candidate-gap mapping; candidates remain unimplemented until the port checkpoint.
- **Asset inventory:** file names, byte sizes and source blob hashes captured; exact target-path gaps are listed above.
- **Component/runtime wiring:** intentionally not part of A acceptance; still pending.
- **Checkpoint A status:** `inventory complete / implementation in progress`; no phase completion is inferred from this document.


## Exact component-copy reconciliation — 2026-10-24

Commit [`fb526a2`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/fb526a246dcced5970271086126ee94c8024716e) restored the 13 reference components whose copied target content had diverged from the reference source. A fresh tree comparison after that commit confirms **25/25** `apps/web/components/reference-ui/*.tsx` component blob SHAs exactly match the corresponding `components/*.tsx` blob SHAs from reference tree `5184f44e9f6c4e641cbe37e9f743583cf40d785e`.

This exact-copy result is deliberately limited to the source component folder. It is **not** runtime wiring, API integration, or visual acceptance. Keep these source files isolated from canonical routes until the source-first UI port checkpoint wires them to existing routes with the required compatibility adaptations. Do not replace canonical `apps/web/app/page.tsx` with the reference's demo-state orchestrator.

## Focused parity pass — Post Detail route (2026-10-24)

- Added canonical dynamic route `/posts/[postId]` using the reference's Post Detail route intent while preserving the canonical API as the source of truth.
- The page reads the authenticated session from Supabase Auth and fetches `GET /v1/feed/item/{content_id}`; it renders real API content/media, loading, unavailable/error and retry states. Reaction, save and share actions call the existing Feed API contracts and refresh from the server; no sample post collection or client-side business writes are introduced.
- The route is intentionally a focused visual/route slice, not a claim that all Post Detail reference interactions or comments are complete. The copied `PostDetailView.tsx` remains source material until its reference-specific prop/state contract is adapted without importing `lib/store.ts` sample data.
- Validation: source file created on `eng-ui-checkpoint-c-navigation-shell`; TypeScript/build/smoke and authenticated runtime have not yet been executed/verified in this session.
- Next in the existing owner phases: audit endpoint/service/schema ownership before creating runtime pages for AI Cinema, Live Stage and Marketplace; route shells must not imply unsupported backend capabilities. Keep UI parity and affected phases `in_progress`.

## Focused parity pass — AI Cinema, Live Stage, Marketplace (2026-10-24)

- **AI Cinema route `/cinema`:** Added a canonical library page backed by authenticated `GET /v1/content/mine?limit=100` and owner-authorized `GET /v1/content/{content_id}/preview`. It renders only the current user's actual video/audio content, status, moderation state and short-lived preview URLs. It links to the existing Create route. It explicitly does not claim to generate films: the audited backend exposes content draft/upload/preview/publish/retry lifecycle, but no cinematic generation/render-job contract was found. The reference `AiCinemaView.tsx` contains `INITIAL_MOVIES_LIST` and hard-coded sample film data, so it is not mounted as a live catalogue.
- **Live Experience route `/live`:** Added a reference-aligned stage presentation with truthful integration status and links to existing Communities/Messages routes. The inspected canonical Supabase schema has no live session/participant/streaming tables, and the FastAPI route inventory has no live session/signaling/provider endpoints. Start-broadcast is disabled; no fake viewer counts, live state, camera/microphone success, or session creation is presented. Full ENG-P25/P26 and related ENG-P27 behavior requires a provider, versioned API contracts, schema/migrations, authorization, reconnect/partial-failure handling and tests.
- **Marketplace route `/marketplace`:** Added discovery from the existing public `GET /v1/skill-catalog` and `GET /v1/spatial/themes` endpoints. These sources return metadata-only Skill blueprints and published Themes; the page does not infer that a blueprint is executable or that a Theme is purchasable. Purchase/pricing/order/subscription controls are intentionally absent because canonical commerce and ledger endpoints/contracts are not present in the audited API/schema. ENG-P28/P29/P30 remain the owning phases for actual listing eligibility, commerce and settlement.
- **Shared navigation:** The existing reference navigation now routes Film AI → `/cinema`, Live Stage → `/live`, Marketplace → `/marketplace`, maps the selected tab by route, and hides bottom navigation on `/posts/[postId]`.
- **Regression guard:** Added smoke-test source assertions for the three routes, their API contracts, route mappings and explicit absence of demo collections/purchase prices/fake live counts. The script has been edited but not executed in this session; assertions are not test-pass evidence.
- **Canonical data audit:** Read the active AllphaAiAplikasi-db project `dvdziauyvuhcnqhrrvww` through the Supabase connector. Existing `content_items`/`content_media` and published Theme registry support the implemented reads. The current public schema has no dedicated live-session, cinematic-render-job, marketplace-listing/order/payment tables. No database mutation or migration was applied.
- **Status:** Source implementation only; TypeScript, lint, smoke execution, build, authenticated browser, visual comparison and end-to-end behavior remain **NOT VERIFIED**. Keep ENG-P13–P16, ENG-P25–P30 and overall parity `in_progress` according to their existing owners; do not create new phases or claim the full domain is complete.

## Focused parity pass — Human Profile route (2026-10-24)

- Added `/profile` as the Human Profile route, backed by Supabase Auth session + FastAPI `GET /v1/me` and `PATCH /v1/me/profile`. It edits only the authenticated user's canonical profile fields (display name, username, avatar URL, bio, visibility), and includes loading, validation, error/retry and save feedback states.
- Added a route link from Agent Identity so Human Profile and AI Agent identity remain distinct but reachable in the UI.
- No direct Supabase browser table writes, sample profile data, or changes to the existing API/schema were introduced.
- Source smoke assertions were added; execution and TypeScript/build/authenticated browser validation remain unverified.


## Focused parity pass — Explore route entry (2026-10-24)

- Added `/explore` as the canonical entry point for the reference Explore/Allpha Hub navigation.
- The route delegates to the existing `/search` implementation and preserves a supplied `q` query. It does not duplicate search logic or introduce sample trends/recommendations; `/search` remains the API-backed owner of search, trends and recommendations.
- Updated the reference navigation's Explore tab to target `/explore` and map it as the active tab. Navbar global search continues to submit directly to `/search?q=…`.
- Added smoke-test source assertions for the Explore route and active navigation contract. CI execution is pending; this is not yet a test-pass claim.
- This is route/navigation parity only. A visual/runtime comparison against `ExploreView.tsx` and its `AllphaHubView` composition remains open; demo/local data from the reference is not used as production truth.


## Focused parity pass — Splash → Auth → Agent onboarding → Feed (2026-10-24)

- The unauthenticated Web entry now presents a Splash/Welcome step first, with explicit actions for sign-in or account creation. These actions switch to the existing canonical Supabase Auth form; they do not create local/demo accounts.
- Successful sign-in or sign-up with a session continues to `/start`. That route verifies the session and fetches the current user's Agent identities through FastAPI before routing to `/feed` or `/agents?onboarding=required`. If the backend cannot verify the identity list, the flow stays fail-closed and presents a retry state.
- Added smoke-test source assertions for Splash actions, Supabase sign-in/sign-up, `/start`, and the Agent-identity gate. CI is queued/pending; these assertions are not yet reported as passing.
- No reference demo state or direct browser business writes were introduced. The full authenticated journey remains unaccepted until CI and browser/API behavior are verified.


## Focused parity pass — entry journey and reference inventory guard (2026-10-24)

- Added a Splash/Welcome state to the unauthenticated root before the existing canonical Supabase sign-in/sign-up form. After authentication, `/start` verifies the current Agent identity through FastAPI and routes to Feed or required Agent onboarding; failures remain retryable and fail closed.
- Added a stable `/explore` entry route that preserves a query and delegates to the existing API-backed `/search` implementation. The reference Explore tab maps to `/explore`; global search remains `/search?q=…`.
- Extended `apps/web/scripts/smoke-test.mjs` to assert the Splash → Auth → Agent gate journey, Explore route/active state, and presence of all 25 top-level reference UI components in the canonical isolated source folder.
- CI found a duplicate top-level identifier in the new smoke assertions. The identifier has been renamed in commit `33b4e5b4d17863f90e53e8addf5971047f471b2c`; the fix still requires a fresh smoke run. Do not treat source assertions as passing until the run completes.
- Remaining scope includes visual/interaction parity for Explore + Allpha Hub, exact responsive comparison across the reference component set, missing binary asset transfer, and route-level validation for all remaining screens. No phase completion is inferred.


## Focused parity pass — Explore Discovery and Messages filters (2026-10-24)

- `/explore` is now a first-class responsive discovery surface rather than a redirect. It loads authenticated FastAPI trends, recommendations, skill catalog, and Spatial themes; keyword search uses `/v1/search`. The page preserves a `q` deep link, and each independent section can render empty data without fabricated cards. Partial API failure is reported without hiding successful sections.
- `/messages` retains canonical conversation/message/read endpoints and Supabase Realtime updates. Added client-side search and Human/AI Agent type filters over the API-returned conversation list; no sample conversation records were imported from `MessagesView.tsx`.
- The reference UI component inventory remains preserved in `components/reference-ui`; the runtime routes use API-backed canonical components rather than mounting the reference demo application.
- Source smoke tests now assert the Explore API surface and Messages API/filter/realtime contracts. The latest Allpha Smoke run for the Explore increment passed; broader Web lint/build and Spatial/Platform workflow runs were still running at the last inspection. Vercel checks continue to report the provider build-rate-limit failure; this is not a successful production deployment.
- Scope remains `in_progress`. Remaining parity work includes a component-by-component visual comparison against the source, full Feed/Reels/Profile/Agent workspace interactions, Spatial theme/scene/GLB behavior, responsive screenshots, and final route/API acceptance. No phase is declared complete from source assertions alone.

## Reference-source preservation slice (2026-10-24)

- The exact upstream component source from `urbanrealty36-ops/Allpha-Front-End-UI-New@main` is preserved in `apps/web/components/reference-source/` for the 25 primary components: BottomNav, Navbar, FeedView, ReelsView, ProfileView, ExploreView, AllphaHubView, AuthOnboardingFlow, AgentGoalsTasksModal, AgentIdentityModal, AskAiModal, AskAiView, AiCinemaView, LiveExperienceStage, MarketplaceView, MessagesView, CreatePostModal, GenerateModal, PostDetailView, SkillsChallengeHub, TakeoverControlView, TakeoverModal, ThreeWorldView, Universe3DExperience, Universe3DHubView.
- Exact upstream app shell files are preserved under `apps/web/reference-source/app/` (page, globals CSS, layout, manifest), and shared source is preserved under `apps/web/reference-source/lib/` and `apps/web/reference-source/hooks/` (store, utils, PWA install hook, mobile hook).
- This is source preservation, not yet proof of runtime mounting or visual parity. The copied reference app remains isolated; its reference-only state/demo content must not become canonical business data. Runtime adapters and actual page-by-page screenshot comparison remain in progress.
- PRD source authority and fixed-plan acceptance gate were updated in this branch. Do not declare completion until the copied source is actually used in the canonical application and screenshot/interaction evidence passes.

