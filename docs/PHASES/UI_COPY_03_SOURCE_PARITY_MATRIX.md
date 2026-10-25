# UI-COPY-03 — Reference UI Domain Port Matrix

**Source of truth:** [Allpha-Front-End-UI-New](https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New), main source tree pinned in the fixed phase plan. **Target:** `apps/web` (Next.js PWA). Native remains `apps/client` (React Native + Expo).

This is a source-to-domain implementation tracker, not a declaration of completion. Preserve reference component DOM, Tailwind class hierarchy, labels, iconography, layout and responsive behavior. Adapters may change data and event handlers only where required to prevent demo state from becoming business truth.

| Reference source view / component | Existing target / route | Current handling | Next action / owner |
|---|---|---|---|
| `FeedView.tsx` | `/feed`, `apps/web/components/reference-ui/FeedView.tsx` | Copied; existing route uses canonical content flow | Compare source-to-route wiring and interaction/error states; existing social/content owner phase |
| `ExploreView.tsx` | `/search`, `/communities` | Copied; search route uses API-backed results/trends/recommendations | Reconcile communities and explore navigation; existing discovery/community owner phase |
| `ReelsView.tsx` | `/reels` | Copied; dedicated route exists | Check all source interactions against media/feed API; no local fake engagement |
| `MessagesView.tsx` | `/messages` | Copied; dedicated route exists | Verify source parity and canonical messaging events/endpoints |
| `ProfileView.tsx` | Agent routes under `/agents` | Component copied; routes are Agent-focused | Map Human profile and Agent passport/studio separately to existing identity/Agent owners |
| `AuthOnboardingFlow.tsx` | `/login`, `/agents?onboarding=required` | Source component uses Auth/FastAPI adapter | UI-COPY-02 code/CI gate recorded; live identity journey intentionally not tested |
| `CreatePostModal.tsx` | `/create` | Copied; dedicated route exists | Keep canonical post creation API; remove any false success or local-only publish |
| `PostDetailView.tsx` | `/feed` interaction | Copied; route-local detail wiring still needs parity review | Map comments/reactions to existing content endpoints |
| `MarketplaceView.tsx` | `/marketplace` | Route added; source layout retained; demo listings/likes/purchase removed; empty catalog fail-closed | Existing ENG-P18 + Booth/Tenant owner phase: typed listing API, canonical tenant/booth join, authorization, lifecycle, purchase/ledger |
| `ThreeWorldView.tsx`, `Universe3DExperience.tsx`, `Universe3DHubView.tsx` | `/spatial/navigation`, `/spatial/[sceneKey]`, `/spatial/themes` | Sources copied; route-by-route source parity not complete | Wire to canonical World/District/Zone/Booth engine; Marketplace Booth 3D must reuse canonical Booth identity |
| `AllphaHubView.tsx` | No dedicated canonical route yet | Component copied, but source contains simulated quests, credit rewards, ledger balances, bookings and event records; it must not be mounted with those defaults | Existing Discovery/Universe, Live Experience, Ads/Booth and Credits/Billing owner phases; add canonical event/quest/surface APIs before wiring interactions |
| `LiveExperienceStage.tsx` | Existing spatial navigation / live surfaces | Copied; dedicated source-faithful route mapping incomplete | Existing Live Experience owner phase; use canonical sessions and explicit unavailable states | Source component currently initializes fake live state, viewer/like counters and slide/audio simulations; route wiring must wait for canonical Live Session state and media controls.
| `SkillsChallengeHub.tsx` | `/skill-challenges` | Copied; route uses canonical skill-challenge APIs | Compare reference screen composition and all actions; no fake rewards/results |
| `AiCinemaView.tsx` | `/ai-cinema` | Dedicated route wired to the copied reference component; sample catalog removed; empty/unavailable state only; publish, approval and VIP billing fail closed | Existing content/media pipeline, Agent Runtime, moderation and billing owner phases: typed catalog/create/upload/verification/subscription/ledger contracts; no demo film, rating, views, credit balance or fake publish success |
| `AskAiView.tsx`, `GenerateModal.tsx`, `AskAiModal.tsx` | `/content-studio` and Agent interaction surfaces | Copied; not all reference flows have dedicated routes | Existing content-generation/Agent runtime owner phases; fail closed without job/credit contracts |
| `TakeoverControlView.tsx`, `TakeoverModal.tsx`, `AgentIdentityModal.tsx`, `AgentGoalsTasksModal.tsx` | Agent routes / account | Copied; full interaction mapping incomplete | Existing Agent runtime, permission and identity owner phases |
| `Navbar.tsx`, `BottomNav.tsx` | `ReferenceNavigation.tsx` | Copied and wired to routes; Marketplace now targets `/marketplace` | Check every nav action has an appropriate canonical route; no dead or misdirected items |
| `app/globals.css`, `app/layout.tsx`, `app/manifest.ts`, icon/public assets | Target Web layout, CSS, manifest and public tree | Partial parity; inventory shows binary asset and config gaps remain | UI-COPY-01/05: compare dependencies, CSS, metadata, fonts/icons, exact public asset paths and manifest/install hooks |

## Execution update — UI-COPY-03 (2026-10-25)

- CI correction evidence: initial build failure on commit `79ccbc3` exposed a duplicate VIP handler; fixed by commit [`3f3cda2`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/3f3cda28ed2e4c46e2816e570fe913ea76c7484b). The Playwright route matrix now includes `/ai-cinema` at all four existing viewports (commit [`a5d95d9`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/a5d95d93e89e816692944840e0fc3bb78457e4ae)); the rerun result is pending.

- The reference `AiCinemaView.tsx` is now routed at `/ai-cinema`, and the `FILM_AI` navigation entry resolves to that dedicated route; `/content-studio` remains the canonical content studio route.
- Removed the source component's hard-coded initial film catalog and fake starter episode files. The screen receives an empty catalog until the canonical API exists. Static royalty/balance claims were removed or made explicitly dependent on canonical ledger/billing state.
- Publish, verification and VIP subscription actions remain fail-closed while `catalogState="unavailable"`; they do not create local business records or report success.
- This is UI route/component wiring only. AI Cinema backend architecture, media job lifecycle, moderation/verification, subscription, payment and royalty settlement remain feature gaps to record under existing domain owners; no new ENG phase is created.
- Checks so far: GitHub blob-SHA parity audit confirms 23 of 27 reference component files checked are byte-identical in the target; `AuthOnboardingFlow.tsx`, `MarketplaceView.tsx`, and `Navbar.tsx` differ intentionally or require adapter review; global CSS and store/assets still require a complete inventory. No build or CI run has yet been executed for this change.

## Source inventory exclusions (intentional)

- `app/page.tsx` and `lib/store.ts` in the reference repository are demo composition/data sources with seeded identities, posts, credits and transactions; they are not copied into production routes as business truth.
- `app/api/agent/interact/route.ts` is not ported as a feature-local Gemini/provider endpoint; AI interactions must use the canonical FastAPI AI Gateway/Model Router.
- Reference UI assets found under `public/` are accounted for in the target `apps/web/public/` tree; the reference manifest mentions PNG icons that are not present in the source public tree, so the target keeps its existing verified SVG icon instead of pointing the PWA manifest at missing files.

## Hard boundaries

- No demo credits/balances, hard-coded Marketplace inventory/prices/likes, local purchase simulation, fake post success, synthetic social records or fake AI reward/settlement can be production state.
- No Marketplace purchase until the canonical API and transaction/ledger contracts are implemented by their existing owner phases.
- No duplicate product/asset registry: a Marketplace listing references the canonical Booth/Tenant identity; a GLB asset ID is not a substitute for listing ID or tenant ID.
- Keep CSS/framework configuration within the existing monorepo; do not overwrite root package scripts, lockfile, auth/security middleware, or app boundaries from the source repository.
- No staging, production-smoke, real-user, or physical-device tests are in scope for this execution. CI/source checks are allowed but must be reported as such.
- Overall UI-copy completion requires file-level source mapping, missing-asset accounting, route/component wiring, and CI/source evidence. A copied component alone does not prove visual or runtime parity.