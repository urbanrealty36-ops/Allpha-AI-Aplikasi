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
