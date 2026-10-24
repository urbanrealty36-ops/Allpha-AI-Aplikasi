# Checkpoint A — Reference UI/UX Source-to-Target Inventory

**Status:** INVENTORY RECORDED / RECONCILIATION PARTIAL  
**Date:** 2026-10-24  
**Reference repository:** `urbanrealty36-ops/Allpha-Front-End-UI-New`, branch `main`  
**Reference tree SHA observed:** `5184f44e9f6c4e641cbe37e9f743583cf40d785e` (recorded in the existing fixed phase plan; recheck before the next port batch)  
**Canonical repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`, branch `main`  
**Canonical HEAD at inventory capture:** `2bb310d4e7b5db10135aa0fb4b9e51623bdab4b6`  
**Scope:** inventory and reconcile existing changes only. This checkpoint does not add product features, wire new API behavior, or deploy.

## 1. Decision and working boundaries

Checkpoint A follows the ordered execution checkpoints already recorded in `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md`; it is not a new ENG phase. The fixed phase plan and `AGENTS.md` remain authoritative. Keep the work frontend-only until the source-porting checkpoint is accepted. Railway is out of scope; Vercel is the only deployment target when deployment is explicitly authorized.

The reference app is a Next.js app with a root view/tab orchestrator and shared component state. The canonical application is a monorepo whose routes and server-backed data flows already exist. Therefore:
- Copy visual source and component hierarchy faithfully.
- Adapt imports, type boundaries, route boundaries and media handling only when necessary for canonical architecture.
- Do not copy local/sample state, demo balances, fabricated people/posts, simulated alerts, or fake success as production behavior.
- Do not replace canonical API/service logic with the reference store.
- Do not call UI parity or integration complete merely because a component file exists.
- Keep archived `.reference` snapshots out of the TypeScript/build graph.

## 2. Component inventory — source → target → feature → status

All 25 top-level reference `components/*.tsx` files were found in the reference repository tree. A matching file currently exists under `apps/web/components/reference-ui/` for each of the 25. “COPIED” means a target file exists; it does **not** mean it is imported by a canonical route, visually verified, integrated with production data, or build-verified.

| # | Reference source | Canonical target | Feature / responsibility | Copy status | Runtime / integration status |
|---:|---|---|---|---|---|
| 1 | `components/AgentGoalsTasksModal.tsx` | `apps/web/components/reference-ui/AgentGoalsTasksModal.tsx` | AI Agent goals, tasks and task-oriented modal | COPIED | Route wiring and canonical Agent API/policy mapping NOT VERIFIED |
| 2 | `components/AgentIdentityModal.tsx` | `apps/web/components/reference-ui/AgentIdentityModal.tsx` | AI Agent identity creation/onboarding | COPIED | Canonical identity onboarding flow NOT VERIFIED |
| 3 | `components/AiCinemaView.tsx` | `apps/web/components/reference-ui/AiCinemaView.tsx` | AI Cinema / film and creator experience | COPIED | Media jobs, entitlements, storage and ledger mapping NOT VERIFIED |
| 4 | `components/AllphaHubView.tsx` | `apps/web/components/reference-ui/AllphaHubView.tsx` | Allpha hub / community discovery experience | COPIED | Canonical community data and route wiring NOT VERIFIED |
| 5 | `components/AskAiModal.tsx` | `apps/web/components/reference-ui/AskAiModal.tsx` | Ask AI modal entry point | COPIED | Canonical agent/runtime endpoint mapping NOT VERIFIED |
| 6 | `components/AskAiView.tsx` | `apps/web/components/reference-ui/AskAiView.tsx` | Ask AI conversation/workspace view | COPIED | Model router, permissions, memory and usage/credits mapping NOT VERIFIED |
| 7 | `components/AuthOnboardingFlow.tsx` | `apps/web/components/reference-ui/AuthOnboardingFlow.tsx` | Human sign-up/login/onboarding journey | COPIED | Must preserve canonical Supabase Auth and server profile provisioning; route parity NOT VERIFIED |
| 8 | `components/BottomNav.tsx` | `apps/web/components/reference-ui/BottomNav.tsx` | Mobile bottom navigation and active tab | COPIED | Shell currently references it; complete route/active-state audit PENDING |
| 9 | `components/CreatePostModal.tsx` | `apps/web/components/reference-ui/CreatePostModal.tsx` | Create/publish post composer | COPIED | Upload, moderation, publish lifecycle and canonical API mapping NOT VERIFIED |
| 10 | `components/ExploreView.tsx` | `apps/web/components/reference-ui/ExploreView.tsx` | Explore, search and discovery | COPIED | Canonical search/recommendation/trend route mapping NOT VERIFIED |
| 11 | `components/FeedView.tsx` | `apps/web/components/reference-ui/FeedView.tsx` | Social Feed composition/cards | COPIED | Canonical Feed route remains separately API-backed; visual composition parity NOT VERIFIED |
| 12 | `components/GenerateModal.tsx` | `apps/web/components/reference-ui/GenerateModal.tsx` | AI generation entry/modal | COPIED | Model router, entitlement, credit ledger and job lifecycle NOT VERIFIED |
| 13 | `components/LiveExperienceStage.tsx` | `apps/web/components/reference-ui/LiveExperienceStage.tsx` | Live stage/session experience | COPIED | Live session lifecycle, media permissions and provider integration NOT VERIFIED |
| 14 | `components/MarketplaceView.tsx` | `apps/web/components/reference-ui/MarketplaceView.tsx` | Marketplace discovery/view | COPIED | Canonical catalog, order, payment and entitlement mapping NOT VERIFIED |
| 15 | `components/MessagesView.tsx` | `apps/web/components/reference-ui/MessagesView.tsx` | Direct messages/conversations | COPIED | Canonical conversations, unread/read, send and authorization mapping NOT VERIFIED |
| 16 | `components/Navbar.tsx` | `apps/web/components/reference-ui/Navbar.tsx` | Global header, search, notifications, credits/agent controls | COPIED | Referenced by navigation shell; real balances/notifications must remain server-backed |
| 17 | `components/PostDetailView.tsx` | `apps/web/components/reference-ui/PostDetailView.tsx` | Post detail and social interactions | COPIED | Canonical content/comments/reactions/moderation mapping NOT VERIFIED |
| 18 | `components/ProfileView.tsx` | `apps/web/components/reference-ui/ProfileView.tsx` | User profile view/edit | COPIED | Must use canonical profile endpoints; complete route wiring NOT VERIFIED |
| 19 | `components/ReelsView.tsx` | `apps/web/components/reference-ui/ReelsView.tsx` | Short-form media/Reels player | COPIED | Current canonical `/reels` route is API-backed; the reference view is not yet proven integrated there |
| 20 | `components/SkillsChallengeHub.tsx` | `apps/web/components/reference-ui/SkillsChallengeHub.tsx` | Skills, challenges and progression hub | COPIED | Canonical skill catalog/challenges/rewards mapping NOT VERIFIED |
| 21 | `components/TakeoverControlView.tsx` | `apps/web/components/reference-ui/TakeoverControlView.tsx` | AI Agent takeover/control panel | COPIED | Consent, permission scopes, audit and server authorization NOT VERIFIED |
| 22 | `components/TakeoverModal.tsx` | `apps/web/components/reference-ui/TakeoverModal.tsx` | Takeover confirmation/modal | COPIED | Canonical takeover policy/action wiring NOT VERIFIED |
| 23 | `components/ThreeWorldView.tsx` | `apps/web/components/reference-ui/ThreeWorldView.tsx` | 3D world renderer/view | COPIED | Must consume canonical scene/asset manifest; visual/runtime acceptance NOT VERIFIED |
| 24 | `components/Universe3DExperience.tsx` | `apps/web/components/reference-ui/Universe3DExperience.tsx` | 3D universe immersive experience | COPIED | Canonical spatial route/renderer/assets integration NOT VERIFIED |
| 25 | `components/Universe3DHubView.tsx` | `apps/web/components/reference-ui/Universe3DHubView.tsx` | Universe 3D hub/navigation | COPIED | Must remain a secondary hub rather than replace Feed-first home; route parity NOT VERIFIED |

## 3. Supporting source, assets and dependency map

| Reference source | Canonical target / current state | Feature | Status / dependency |
|---|---|---|---|
| `app/page.tsx` | Canonical `apps/web/app/page.tsx` already exists and has its own identity/settings journey | Reference tab/view orchestrator | NOT copied over canonical page; replacing it wholesale would overwrite canonical auth/data flow |
| `app/layout.tsx` | `apps/web/app/layout.tsx` exists; current reference shell wrapper was added in `apps/web/components/ReferenceAppShell.tsx` | Root layout/shell | ADAPTED; runtime behavior/build not yet verified |
| `app/globals.css` | `apps/web/app/globals.css` exists with existing canonical styles plus Tailwind/reference style imports from previous commits | Design tokens, resets, responsive styles | PARTIAL; exact source style parity and CSS conflict audit PENDING |
| `hooks/use-mobile.ts` | `apps/web/hooks/use-mobile.ts` | Responsive/mobile breakpoint hook | COPIED; dependency/use audit PENDING |
| `hooks/usePWAInstall.ts` | `apps/web/hooks/usePWAInstall.ts` | PWA install capability | COPIED; canonical PWA behavior and browser compatibility NOT VERIFIED |
| `lib/store.ts` | `apps/web/lib/reference-store.ts` | Reference view types and local app state | COPIED AS REFERENCE SUPPORT ONLY; must not be used as canonical business data source |
| `lib/utils.ts` | `apps/web/lib/reference-utils.ts` | Class/style utility helpers | COPIED; utility/dependency parity PENDING |
| `package.json` | `apps/web/package.json` | UI dependencies | Previous commits added `clsx`, `lucide-react`, `tailwind-merge`, `@google/genai`, `class-variance-authority`, `motion`, `tw-animate-css`, Tailwind v4/PostCSS dependencies; version compatibility and lockfile consistency MUST be checked |
| Reference `postcss.config` | `apps/web/postcss.config.mjs` | Tailwind/PostCSS build chain | ADDED; frontend build/typecheck NOT VERIFIED in this checkpoint |
| Reference images/screenshots | `public/assets/aistudio/` snapshot contains 8 JPEG transfers noted in the fixed plan | Screens, imagery and visual reference | PARTIAL; full image/PNG/font/icon/other binary inventory and checksum reconciliation PENDING |
| Reference `public/*` and non-code assets | Matching complete target paths not established | Icons, fonts, GLB/media assets if present | NOT FULLY INVENTORIED; do not claim copied |
| Reference source tree | `docs/reference-ui-source/Allpha-Front-End-UI-New/` archived `.reference` source snapshot | Reviewable source capture | Existing source archive; compare archive contents against current source tree before using as sole snapshot |

### Dependency inventory (source-level; exact package imports still need a per-file pass)

- Framework: Next.js App Router, React and TypeScript.
- Styling: Tailwind CSS v4 / `@tailwindcss/postcss`, `tw-animate-css`, CSS global styles.
- UI primitives: `lucide-react`, `clsx`, `tailwind-merge`, `class-variance-authority`.
- Animation: `motion`.
- 3D: `three`; canonical app also uses `@react-three/fiber`. Validate compatibility before importing reference 3D views.
- AI SDK: reference dependency `@google/genai` is present in package manifests; direct client SDK calls must not be adopted as a substitute for canonical AI Gateway/Model Router.
- Canonical platform dependencies: Supabase JS client exists in the canonical app, but business operations must follow the established FastAPI/API contract and canonical service boundaries.
- Required validation: dependency/lockfile consistency, import graph, typecheck, lint, smoke/build and route-level visual/interaction review. These have not all been proven by this inventory.

## 4. Route/shell reconciliation — what is already in main

| Canonical file/route | Observed change on main | Assessment |
|---|---|---|
| `apps/web/components/reference-ui/ReferenceNavigation.tsx` | Added a shell wrapper using reference `Navbar` and `BottomNav`; maps paths to tabs | PRESENT; search/navigation callbacks and all routes still need audit |
| `apps/web/components/ReferenceAppShell.tsx` | Added to mount navigation on routes except `/` and `/start` | PRESENT; root/auth journey and duplicate navigation need browser verification |
| `apps/web/app/layout.tsx` | Wrapped app children with `ReferenceAppShell` | CHANGED; check metadata/layout behavior and duplicate shell/header across all routes |
| `apps/web/app/globals.css` | Added Tailwind and animation imports in earlier commits | CHANGED; not evidence of full reference CSS port |
| `apps/web/app/feed/page.tsx` | Navigation import/render removed after global shell; a malformed empty conditional was fixed in a later commit | CHANGED; canonical Feed data logic retained, but full reference FeedView parity is not complete |
| `apps/web/app/reels/page.tsx` | Navigation render removed after global shell | CHANGED; remains the existing API-backed page; no committed ReelsView integration is evidenced by the current source hash |
| `apps/web/app/messages/page.tsx` | Navigation render removed after global shell | CHANGED; canonical page remains; MessagesView integration NOT VERIFIED |
| `apps/web/app/search/page.tsx` | Navigation render removed after global shell | CHANGED; ExploreView integration NOT VERIFIED |
| `apps/web/app/stories/page.tsx` | Navigation render removed after global shell | CHANGED; reference Stories source is not a separate top-level component in the 25-file inventory; page parity NOT VERIFIED |
| `apps/web/app/agents/page.tsx` | Navigation render removed after global shell | CHANGED; Profile/Agent Identity/Takeover component wiring NOT VERIFIED |
| `apps/web/app/communities/page.tsx` | Navigation render removed after global shell | CHANGED; AllphaHubView wiring NOT VERIFIED |
| `apps/web/app/skill-challenges/page.tsx` | Navigation render removed after global shell | CHANGED; SkillsChallengeHub wiring NOT VERIFIED |
| `apps/web/app/workflows/page.tsx` | Navigation render removed after global shell | CHANGED; AI Cinema/creation workflow parity NOT VERIFIED |
| `apps/web/app/spatial/navigation/page.tsx` | Navigation render removed after global shell | CHANGED; 3D hub/renderer wiring NOT VERIFIED |
| `apps/web/app/spatial/themes/page.tsx` | Navigation render removed after global shell | CHANGED; preserve canonical Theme Builder/manifest logic |
| `apps/web/app/notifications/page.tsx` | Navigation render removed after global shell | CHANGED; Navbar notification callback/real notification behavior NOT VERIFIED |
| `apps/web/tsconfig.json` | Excludes `reference-source/**` | CHANGED; exclusion does not replace checking the actual archived source path/import graph |
| `apps/web/package.json` and `apps/web/postcss.config.mjs` | UI/build dependencies and Tailwind PostCSS config changed | CHANGED; lockfile consistency and successful app build NOT VERIFIED |

### Recent main commits reviewed for reconciliation

| Commit | Message | Checkpoint-A interpretation |
|---|---|---|
| `807774d8c625b7a11708ac58b3a5c3e8a6691408` | `chore(ui): stage complete reference app source and import mapping` | Archived reference source/import mapping; not canonical route integration by itself |
| `3241d81493f75f2fbe0cf7e7f8a37b7fa58f6d17` | `chore(ui): copy reference visual assets into web public assets` | Asset transfer is partial per fixed plan; verify exact asset list/checksums |
| `5970d9b53a12d2433892fc05811b5ba5b5c8a6d1` | `chore(ui): port remaining reference components into web app` | Component files staged; does not establish route wiring |
| `9fdb89f5cea3b7904a7136f8b14ef3d2258bc0dc` | `feat(web): activate reference navigation and Tailwind styling dependencies` | Shell/dependency changes landed; frontend build status still must be checked |
| `cef795f4bd55eae7abc8d66d8cd959a8e7b1a756` | `feat(ui): port remaining reference screens and complete styling dependencies` | Additional component/style changes landed; route parity not implied |
| `7d36565fd2f725ac723409c861e5ef5fc25b4d22` | `fix(web): exclude archived reference source from app typecheck` | Build-graph exclusion changed; must verify intended archived path and no live code excluded |
| `5b196de5034b0da18717d7f77e4ea397b28aaaba` | `feat(web): apply reference navigation shell across authenticated routes` | Global shell activated and per-route nav removed; duplicate/active-route behavior needs validation |
| `239d69007d2a3ca420fa76e4ea42af08f5d52c23` | `fix(web): remove empty conditional left by global navigation migration` | Syntax correction on Feed page |
| `2bb310d4e7b5db10135aa0fb4b9e51623bdab4b6` | `docs(phases): define ordered reference UI parity checkpoints` | Existing phase plan now explicitly defines checkpoints A–H and their exit criteria |

## 5. CI/deployment evidence at the inventory capture point

Latest observed Actions runs for HEAD `2bb310d4e7b5db10135aa0fb4b9e51623bdab4b6`:
- **Allpha Smoke:** completed SUCCESS.
- **ENG-P22 Spatial and Production Quality Gate:** completed FAILURE.
- **ENG-P01 Platform Foundation:** completed FAILURE.

These results are not a Web UI build pass. The specific failing job/step must be inspected in a separate validation slice. No Vercel deployment was triggered during Checkpoint A; no Railway build/deploy was run. Do not infer production visual parity from a smoke workflow.

## 6. Known duplicates, gaps and risk items

1. A reference-source file with suffix `.reference` exists beside `ExploreView.tsx` and `MessagesView.tsx` in `apps/web/components/reference-ui/`; reconcile why both exist and ensure archived snapshots do not enter the runtime import graph.
2. Reference source components are present but most are not yet proven imported by canonical pages. A file-existence check is not a feature completion check.
3. A global shell may overlap with route-specific existing headers or navigation. Check all route layouts before further shell expansion.
4. Source UI demo data and state are not canonical business data. Each view must be inspected for fabricated profiles, counters, balances, alerts, fake success, and local-only mutations before integration.
5. Full binary inventory remains incomplete: image/PNG/font/icon/GLB/media paths and checksums need exact reconciliation.
6. Exact per-file import dependencies, source-to-canonical route/action mapping, native parity mapping and endpoint/service ownership remain follow-up audit items; the broad package list above is not a substitute for the per-file import graph.
7. Current Actions evidence has failed ENG-P01 and ENG-P22 checks. The failures are not diagnosed here, because this checkpoint is inventory-only.

## 7. Checkpoint A acceptance

- [x] Reference tree enumerated: 25 top-level component TSX files.
- [x] Each component has a corresponding canonical reference-ui target path.
- [x] Main commits affecting reference source, dependencies, global shell and canonical routes listed.
- [x] Known route integration gaps, duplicate files, incomplete assets and CI status documented.
- [ ] Per-file imports/dependencies and all image/font/icon/GLB binary paths/checksums fully reconciled.
- [ ] Full source tree parity audit against archived `.reference` snapshots completed.
- [ ] Build/typecheck/lint run with results retained; not part of this inventory-only commit.

**Checkpoint A status: PARTIAL.** The baseline is now traceable, but the remaining unchecked items are explicit. Next permitted action: finish the inventory reconciliation only, or ask the Product Owner to accept this partial baseline before Checkpoint B. Do not begin another broad component port or backend integration from this document alone.
