# UI-COPY-03 — Reference UI Domain Port Matrix

**Source of truth:** [Allpha-Front-End-UI-New](https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New), main source tree pinned in the fixed phase plan. **Target:** `apps/web` (Next.js PWA). Native remains `apps/client` (React Native + Expo).

This is a source-to-domain implementation tracker, not a declaration of completion. Preserve reference component DOM, Tailwind class hierarchy, labels, iconography, layout and responsive behavior. Adapters may change data and event handlers only where required to prevent demo state from becoming business truth.

| Reference source view / component | Existing target / route | Current handling | Next action / owner |
|---|---|---|---|
| `FeedView.tsx` | `/feed`, `apps/web/components/reference-ui/FeedView.tsx` | Copied; existing route uses canonical content flow | Compare source-to-route wiring and interaction/error states; existing social/content owner phase |
| `ExploreView.tsx` | `/search`, `/communities` | Copied; search route uses API-backed results/trends/recommendations | Reconcile communities and explore navigation; existing discovery/community owner phase |
| `ReelsView.tsx` | `/reels` | Copied; dedicated route exists | Check all source interactions against media/feed API; no local fake engagement |
| `MessagesView.tsx` | `/messages` | Copied; dedicated route exists | Verify source parity and canonical messaging events/endpoints |
| `ProfileView.tsx` | `/profile` | Dedicated route mounts the copied component; identity and owned Agents load from `/v1/me` and `/v1/agents`. Static demo owned Agents, fake skill/task counts, KYC/ledger claims and balances are removed/hidden; social counts, posts and credits remain unavailable until canonical data is wired | Continue existing identity/social/feed/Agent owner phases: load social graph counts, actual profile posts, knowledge documents, canonical skill/task state and verified identity metadata; preserve source layout and explicit empty states |
| `AuthOnboardingFlow.tsx` | `/login`, `/agents?onboarding=required` | Source layout retained; form starts blank (no seeded email/password/interests/skills), imports types/catalog from `reference-store`, and submits a typed payload to the existing Supabase Auth + FastAPI adapter. Success is shown only after the adapter resolves; fake +50-credit claim removed. | Validate Auth flow typecheck/build and complete UI-COPY-03 route/viewport gate; backend journey remains untested here |
| `CreatePostModal.tsx` | `/create` | Copied; dedicated route exists | Keep canonical post creation API; remove any false success or local-only publish |
| `PostDetailView.tsx` | `/feed` interaction | Copied; route-local detail wiring still needs parity review | Map comments/reactions to existing content endpoints |
| `MarketplaceView.tsx` | `/marketplace` | Route added; source layout retained; demo listings/likes/purchase removed; empty catalog fail-closed | Existing ENG-P18 + Booth/Tenant owner phase: typed listing API, canonical tenant/booth join, authorization, lifecycle, purchase/ledger |
| `ThreeWorldView.tsx`, `Universe3DExperience.tsx`, `Universe3DHubView.tsx` | `/spatial/navigation`, `/spatial/[sceneKey]`, `/spatial/themes` | Sources copied; route-by-route source parity not complete | Wire to canonical World/District/Zone/Booth engine; Marketplace Booth 3D must reuse canonical Booth identity |
| `AllphaHubView.tsx` | No dedicated canonical route yet | Component copied, but source contains simulated quests, credit rewards, ledger balances, bookings and event records; it must not be mounted with those defaults | Existing Discovery/Universe, Live Experience, Ads/Booth and Credits/Billing owner phases; add canonical event/quest/surface APIs before wiring interactions |
| `LiveExperienceStage.tsx` | `/live` | Dedicated source-component route added; UI layout retained; no sample viewer/like counts or sample chat; live, chat, mic/camera, takeover and slide controls fail closed until canonical session API adapter exists | Existing Live Experience owner phase: connect session/media/chat/presence/likes/takeover and presentation endpoints; keep explicit empty states until available |
| `SkillsChallengeHub.tsx` | `/skill-challenges` | Copied; route uses canonical skill-challenge APIs | Compare reference screen composition and all actions; no fake rewards/results |
| `AiCinemaView.tsx` | `/ai-cinema` | Dedicated route wired to the copied reference component; sample catalog removed; empty/unavailable state only; publish, approval and VIP billing fail closed | Existing content/media pipeline, Agent Runtime, moderation and billing owner phases: typed catalog/create/upload/verification/subscription/ledger contracts; no demo film, rating, views, credit balance or fake publish success |
| `AskAiView.tsx` | `/ask-ai` | Dedicated source component route added; identity and active Agent are loaded from `/v1/me` and `/v1/agents`; direct `/api/agent/interact`, local fallback reply and credit reward removed. Chat remains unavailable until a canonical conversational Agent Runtime endpoint/contract is exposed | Existing ENG-P05/P06/P09/P10/P11: add authenticated Agent Runtime conversation/session contract; do not fake chat responses or deduct credits locally |
| `GenerateModal.tsx`, `AskAiModal.tsx` | Create/feed/Agent interaction surfaces | Components copied but no full route-specific adapters | Existing content/media and Agent Runtime owners: canonical job creation, status polling and cancellation; explicit unavailable state until API contracts exist |
| `TakeoverControlView.tsx`, `TakeoverModal.tsx`, `AgentIdentityModal.tsx`, `AgentGoalsTasksModal.tsx` | Agent routes / account | Six modal sources have target counterparts; four are byte-identical. `AgentIdentityModal` retains source DOM/classes and uses target reference-store catalog/types; persistence of avatar/bidang/model/skills is not wired because current `/v1/agents` contract does not expose those fields. `AgentGoalsTasksModal` preserves source UI hierarchy/forms but now fails closed for local-only task/goal writes, progress changes, autonomous toggles and simulated execution; no success is fabricated. It has no mounted route integration currently. | Existing Agent identity/runtime owner phases must provide typed canonical contracts and mount adapters before these actions are enabled; UI-COPY-03 must not invent API routes or persist component-local state |
| `Navbar.tsx`, `BottomNav.tsx` | `ReferenceNavigation.tsx` | Copied and wired to routes; Marketplace now targets `/marketplace` | Check every nav action has an appropriate canonical route; no dead or misdirected items |
| `app/globals.css`, `app/layout.tsx`, `app/manifest.ts`, icon/public assets | Target Web layout, CSS, manifest and public tree | Partial parity; inventory shows binary asset and config gaps remain | UI-COPY-01/05: compare dependencies, CSS, metadata, fonts/icons, exact public asset paths and manifest/install hooks |

## Execution update — UI-COPY-03 (2026-10-25)

- CI correction evidence: initial build failure on commit `79ccbc3` exposed a duplicate VIP handler; fixed by commit [`3f3cda2`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/3f3cda28ed2e4c46e2816e570fe913ea76c7484b). The Playwright route matrix now includes `/ai-cinema` at all four existing viewports (commit [`a5d95d9`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/a5d95d93e89e816692944840e0fc3bb78457e4ae)); the rerun result is pending.

- The reference `AiCinemaView.tsx` is now routed at `/ai-cinema`, and the `FILM_AI` navigation entry resolves to that dedicated route; `/content-studio` remains the canonical content studio route.
- Removed the source component's hard-coded initial film catalog and fake starter episode files. The screen receives an empty catalog until the canonical API exists. Static royalty/balance claims were removed or made explicitly dependent on canonical ledger/billing state.
- Publish, verification and VIP subscription actions remain fail-closed while `catalogState="unavailable"`; they do not create local business records or report success.
- This is UI route/component wiring only. AI Cinema backend architecture, media job lifecycle, moderation/verification, subscription, payment and royalty settlement remain feature gaps to record under existing domain owners; no new ENG phase is created.
- Checks so far: GitHub blob-SHA parity audit confirms 16 of 25 reference component files are byte-identical in the target; nine are adapted for canonical imports or to remove demo state and wire safe routes: `AgentGoalsTasksModal.tsx`, `AgentIdentityModal.tsx`, `AiCinemaView.tsx`, `AskAiView.tsx`, `AuthOnboardingFlow.tsx`, `LiveExperienceStage.tsx`, `MarketplaceView.tsx`, `Navbar.tsx`, and `ProfileView.tsx`. The 19 source public assets checked are present in the target `apps/web/public/` tree; `lib/store.ts` remains intentionally excluded because it seeds fake profiles, posts, credits and transactions. No build or CI run has yet been executed for this change.

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

## UI-COPY-03 execution update — 2026-10-25 (Live route/PWA audit)

- Added a dedicated `/live` route that mounts the copied `LiveExperienceStage` component; navigation now maps the source Live Stage tab to `/live`. Code commit: [8612666](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/8612666d3cb5e1ad0f5f09168f238875a59c8dc8), followed by [0df1b4d](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/0df1b4d1b06038c147c9170674ce30cf6e357032) to disable slide controls while no canonical Live session exists.
- Live UI keeps source component structure and Tailwind classes but starts with no live session, no seeded viewers/likes/chat, no fake AI turn-taking, and disabled session controls. Live session, media, chat, presence, takeover and presentation still need canonical FastAPI adapter contracts.
- Expanded responsive visual route list to 13 routes × 4 viewport widths and smoke assertions to cover `/live` and fail-closed Live data. Earlier check for commit `e09617f` failed because source-style viewport settings disabled zoom; this was corrected to preserve `userScalable: true` as required by the canonical accessibility smoke test. The latest run for commit `8612666` was still in progress at the last status read; commit `0df1b4d` triggered another run.
- PWA inventory: the reference `app/globals.css` is only `@import "tailwindcss";` and `@import "tw-animate-css";`; the target preserves those imports in its retained source snapshot and its active stylesheet, without replacing the target's canonical CSS. All 19 source public image/icon assets checked are present under `apps/web/public/`. The source manifest references `icon-192.png` and `icon-512.png`, but neither file exists in source public assets; target therefore retains its existing `/icon.svg` instead of introducing broken icon URLs. Native remains React Native + Expo.
- Remaining UI-COPY-03 blockers are explicit: ProfileView is not mounted because the source component includes hard-coded owned Agents and credit counts; AskAiView still contains a source-era feature-local API call/fallback and has no dedicated canonical route. They must be adapted to canonical identity/social/feed and Agent Runtime contracts before mounting; do not seed profiles, balances, chat responses or fake success. See `UI_COPY_03_SOURCE_PARITY_MATRIX.md`.
- No claim of phase completion or production deployment is made. CI/build/visual checks for the latest commits must be confirmed before closing UI-COPY-03.


**Additional execution update (2026-10-25 — Ask AI route):** Added `/ask-ai` using the copied `AskAiView` and an adapter that loads authenticated Human identity (`/v1/me`) and Agent catalog (`/v1/agents`). The source feature-local `/api/agent/interact` call and generic success fallback were removed. Until a canonical conversational Agent Runtime API is available, the screen shows an empty conversation and an explicit unavailable message; no local credits or fabricated replies. Commits: [a3d5567](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/a3d5567ce8735838c4a74051c3a7bbba6fc64f19), [c34bfc1](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/c34bfc12b063e621a4d3ba9ec5138b3ff54d49ef), [4a7cf9d](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/4a7cf9d6b8ecb9539a417616126496b096c6ade1). Visual route matrix expanded to 13 routes × 4 viewports. Human `ProfileView` now mounts at `/profile` with canonical identity and owned-Agent adapter; social counts/posts/knowledge/skills/tasks remain empty until canonical endpoints are connected.


**UI-COPY-03 execution update (2026-10-25 — Profile route):**
- Added `/profile` using the copied `ProfileView` component. Authenticated Human identity and owned Agent records are loaded through `/v1/me` and `/v1/agents`; no demo-owned Agents, fake credit totals, seeded skill/task counts, KYC status or ledger hash are shown. Social counts, feed posts, knowledge docs, skill catalog and task records remain explicit unavailable/empty until canonical endpoints are wired. Profile edits route to the canonical account screen; Agent mutation controls stay disabled without an update API adapter.
- Code commits: [100bc9f](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/100bc9ff98366f4d989d438fa00a87eb41098184), [e87f10c](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/e87f10caa6c8bc9b821dac07d91c22bfb82de46f), [7126cf1](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/7126cf1acc864bc2bc40bd355218aff568826a0b). The first build exposed a malformed trailing-slash regex in the new route; fixed in `7126cf1`. The current build/visual checks must pass before closing this slice.


## Current UI-COPY-03 status — 2026-10-25 (authoritative checkpoint)

- Source-to-target component audit: **25/25 components present**, **16 byte-identical**, **9 adapted**; 19/19 source public assets checked are present. `use-mobile.ts` and `usePWAInstall.ts` match source blob SHA exactly. Source `app/globals.css`, `app/manifest.ts`, and `app/layout.tsx` are retained as exact source snapshots; active target CSS is not overwritten because it also styles canonical app surfaces. PWA icon manifest keeps existing `/icon.svg` because source manifest references PNG icon files absent from the source public tree.
- Dedicated routes now exist for `/ai-cinema`, `/live`, `/ask-ai`, and `/profile`. `/live` is fail-closed without canonical session data. `/ask-ai` uses `/v1/me` and `/v1/agents`, and does not call a feature-local AI endpoint or fabricate answers. `/profile` uses `/v1/me` and filters Agent records by `ownership.owner_user_id` before displaying them; social/feed/knowledge/skill/task data is not fabricated.
- Latest observed CI on code commit `8e31aef`: Web typecheck/lint/smoke/build **success**, API regression tests **success**, Web renderer **success**, API contract **success**. At last status read, visual route Playwright, native renderer, Android/iOS builds and some aggregate checks were still running. No production deployment is claimed.
- Remaining acceptance blocker: copied `FeedView`, `ExploreView`, `ReelsView`, and `MessagesView` are present, but their current canonical routes still use existing route components. They need source-faithful route adapters and real API data/actions without seeding reference demo posts, reels, conversations, credit balances or local-success simulations. Continue UI-COPY-03; do not advance the phase owner until this and the responsive route gate are complete.


## Execution update — UI-COPY-03 (2026-10-25, Auth/navigation/PWA source adapter corrections)

- Fixed the onboarding component-to-adapter contract: `AuthOnboardingFlow.tsx` now imports the copied type/catalog module instead of the absent `@/lib/store`, supplies credentials/auth mode/interests/persona with the selected Human/Agent data, awaits the canonical adapter, and only then displays its source-styled success state. Empty form state replaces seeded email/password, default interest selection and default sample skills; the false `+50 AI Credits` claim was removed. Existing Supabase Auth and FastAPI calls in `AuthOnboardingRoute.tsx` remain the business path.
- Navigation no longer invents an unread count (`2`) or passes a hard-coded `0`; a badge appears only if a numeric count is actually supplied. Removed duplicate `/live` active-tab condition.
- PWA viewport now permits user zoom (`userScalable: true`; no `maximumScale: 1`).
- Commits: [f767034](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/f767034829498cf6ef11117eb46b4f10a8422e83), [da8eb3f](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/da8eb3f513840c8b4b2ab9f6e4f28f7a6ed1953e), [303c3ad](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/303c3ad66529a4d57a4e5a45fe771dad4d2f109e), [a1bfd8d](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/a1bfd8d5a39896f57aa86cf184a3c16c4ae408f7), [bab81de](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/bab81de3f374147294c4a5cf4593a9acc50ab7b7).
- Verification boundary: source files and existing API call paths were inspected; no npm build/typecheck/lint or browser viewport run was executed in this pass. Current UI-COPY-03 remains IN_PROGRESS and the 360/390/820/1440 acceptance evidence is still outstanding.


- **Auth catalog follow-up (2026-10-25):** The reference-styled onboarding now fetches its selectable Skills from the canonical FastAPI `/v1/skill-catalog` endpoint (bounded five-page request, deduplicated by canonical key), shows loading/error/empty states, and submits only selected catalog skill names to the existing provisioning adapter. This avoids selecting hard-coded sample skills that cannot be resolved by the backend. Human avatar choices use the existing local app icon instead of random `picsum.photos` identities. Code commit: [ffd5ae0](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/ffd5ae03fdd57af16991ee6b78fae9c347679634). Build/typecheck and Auth runtime flow remain unverified here.


## Execution update — UI-COPY-03 (2026-10-25, Feed/Reels source composition)

- `/feed` directly mounts `FeedView` with API-backed post/story data and canonical callbacks. Loading, error, notice and true-empty states are now rendered inside the copied FeedView post-stream hierarchy, after the reference category tabs, Stories row and Live Stage hero, instead of preceding the entire reference component. Filter-specific unavailable states are kept separate from the general empty-feed state. Commits: [956dbbd](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/956dbbd3335014bcc73a105ccb75b48d08ad0f5c), [f1a27f9](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/f1a27f9ae82ac2f9cefd3f77cd38a840939cec40), [ce65e57](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/ce65e570a2a11358dc933088c00469f8f4b342e5).
- `/reels` now keeps the copied `ReelsView` mounted during initial API loading and uses its existing dark source-style empty container for the loading state; the API adapter still supplies only real items and callbacks. Commits: [65d5f91](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/65d5f91ae2c0e7ec0c5bf95342d898bc879a0377), [b6eeb78](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/b6eeb78fe0cb040a11e138024d504ede5dbcd107).
- This is route composition/state placement work, not proof of visual parity. Search and Messages state placement, selector inventory, component drift, complete CSS/config/assets reconciliation and all requested browser viewport checks remain open.


- **Explore/Search state placement (2026-10-25):** `/search` continues to mount copied `ExploreView` with API-backed search/trend/recommendation data. Search loading, validation/API error, empty results and initial prompt now render inside the reference component content area rather than as route-level elements after the entire view. The query from `?q=` is synchronized into the copied search input. Commits: [d324f66](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/d324f66792d688be55b788e06077eadb6149d70c), [877aac1](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/877aac1fdc7e16fa6adfb27dce212a6ee70d82e6). Build/typecheck and browser behavior remain unverified.


- **CSS selector usage audit (2026-10-25, sampled route families):** Current `globals.css` feature groups are not safe to delete wholesale: `.identity-shell`, `.auth-layout`, `.auth-intro`, `.identity-orbit`, `.auth-panel`, `.social-panel`, `.social-columns` are used by `/account`; `.agent-create`, `.catalog-picker`, `.agent-list-section`, `.agent-card`, `.agent-empty` by `/agents`; `.passport-shell`/`.passport-card` by Agent Passport; `.workspace-grid`, `.workspace-panel`, `.workflow-list`, `.workflow-column`, `.run-row`, `.step-row` by `/workflows`; `.page-shell`, `.page-header`, `.challenge-layout`, `.history-panel` by `/skill-challenges`; `.allpha-stories-page` by `/stories`; and `.allpha-spatial-page` by `/spatial/themes`. These are existing feature-owned styles and remain until their specific route/component is migrated. The earlier route-specific forced palette/Feed/Reels/navigation overrides were removed in the existing scoped CSS pass; no broad CSS deletion was performed in this pass. The selector audit is route-source inspection, not browser-computed-style proof.


- **PWA/config reconciliation (2026-10-25):** Source `app/globals.css` contains only Tailwind 4 and `tw-animate-css` imports; target keeps both imports plus feature-owned CSS required by existing `/account`, Agent, Workflow, Skill Challenge, Stories and Spatial routes. Source `app/manifest.ts` references `icon-192.png`/`icon-512.png`, but source `public/` tree contains neither file; target retains the existing verified `/icon.svg` rather than introducing broken icon URLs. Source PostCSS includes `autoprefixer`, while target uses the existing Tailwind 4 PostCSS plugin and does not add a new dependency/lockfile mutation without build verification. Target layout retains existing metadata and now permits viewport zoom. Source reference main tree inspected: `aad317c1f651163f065cd42b9ae35267d18f354a`. Config parity remains partial; installability and actual asset rendering are not verified in a browser.


- **Messages state placement (2026-10-25):** `/messages` keeps the copied `MessagesView` for the API-backed inbox. Inbox loading/error/notice messages now render inside the reference component after its header/search area; active-conversation API messages and delivery/realtime state remain in the route's conversation view, with error/notice placed inside that view rather than above the whole route. The source `MessagesView` is an inbox list only; the original demo opens an Ask AI modal, so production chat requires the existing canonical messaging API rather than copying demo chat behavior. Commits: [f7ee26a](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/f7ee26adb538fa88e710d295a4a4cdc6812a7596), [565f0c6](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/565f0c6c19c266e0d6e2c9557ec596c3678549e5). Runtime parity remains unverified.


- **Auth credit-claim correction (2026-10-25):** Removed the remaining `Bonus Selamat Datang: +50 AI Credits` claim from the copied onboarding success panel. The flow now has no hard-coded credit bonus message; any future balance must be rendered only from canonical credit-ledger state. Commit: [ce03e85](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/ce03e85f11149fcd2dadb7b3b265b49d42aaa1c5). Source assertion check confirms no `picsum.photos`, no +50-credit success claim, awaited adapter completion, skill loading/error states, and Supabase Auth/FastAPI route calls; this is source inspection, not a run of the smoke script or build.

## Execution update — 2026-10-26: reference component class audit and Navbar correction

Reference source baseline: `urbanrealty36-ops/Allpha-Front-End-UI-New@aad317c1f651163f065cd42b9ae35267d18f354a`.

### Source-to-target component audit

A direct source/target comparison was performed for the 25 top-level React components in the reference repository. The comparison extracted static/template `className` tokens from each source and target component; this is a source-level styling inventory, not a browser-rendered pixel-parity claim.

- All 25 target component files exist under `apps/web/components/reference-ui/`.
- The target retained every detected source class token in the audited component set after the Navbar correction. Some target files intentionally differ in handlers, props, API adapters, or demo-data removal; those differences must not be “fixed” by blindly copying source business state.
- 12 files were byte-identical at this audit checkpoint: `CreatePostModal.tsx`, `GenerateModal.tsx`, `SkillsChallengeHub.tsx`, `ThreeWorldView.tsx`, `Universe3DExperience.tsx`, `Universe3DHubView.tsx`, `BottomNav.tsx`, `AskAiModal.tsx`, `AllphaHubView.tsx`, `PostDetailView.tsx`, `TakeoverControlView.tsx`, and `TakeoverModal.tsx`.
- The other 13 are production-adapted or differ from the reference and still require route/interaction review; 100% class-token presence alone does not prove identical layout, conditional rendering, typography, motion, or behavior.

### Code correction committed

- Restored the reference red notification dot in `apps/web/components/reference-ui/Navbar.tsx` using the original source classes `absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-rose-500 border border-white`.
- The notification dot is purely visual and does not introduce a fabricated unread count. The target's canonical notification callback and API-backed unread-message count remain intact.
- Commit: [61e7045](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/61e7045eefd54a9b390bec4d64af1eb4893973be).

### PWA and route findings

- Reference and target both define `start_url: '/'`, `scope: '/'`, standalone display, and the same theme/background colors.
- The reference manifest names `/icon-192.png` and `/icon-512.png`, but those PNGs are absent from the reference repository tree. The target's existing `/icon.svg` remains the verified icon rather than copying broken manifest paths.
- Production routes `/feed`, `/search`, `/reels`, and `/messages` mount their corresponding reference UI components and use canonical authenticated API flows. The route adapters intentionally suppress demo identities, fake credit balances, sample transactions and simulated success.
- The canonical source phase plan contains WP-01 and WP-02 as ordered work packages, not separate phase-document files. WP-01 is the current UI-COPY-03 source/design-system reconciliation checkpoint; WP-02 is the next package for shared shell, identity, navigation and profile parity. WP-02 must not be marked started/complete until WP-01's exit gates pass.

### Acceptance status — still open

- Not yet verified by this source audit: build, typecheck, lint, automated tests, browser rendering, visual screenshots at 360/390/820/1440 px, install/offline/error PWA behavior, and all route-level interactions.
- The known Feed story viewer route/callback gap remains open. Do not fake a story-open success; reconcile it against a canonical API/route contract.
- Public asset inventory: the reference repository has 23 files under `public/`; the target has 22 corresponding files under `apps/web/public/`. The one source asset not yet copied is `public/assets/aistudio/file_00000000e2f48207b9fbf70131d4041f_fb06dd70.png`. Binary transfer was not available through the current repository-file path, so it remains an explicit WP-01 asset-parity blocker rather than being silently omitted or replaced with invented artwork.
- Separately, the reference manifest points to `/icon-192.png` and `/icon-512.png`, which are absent from the reference public tree. The target's `/icon.svg` remains the existing valid icon; do not switch the manifest to missing PNG paths.
- UI-COPY-03 remains `in_progress`; WP-02 remains next in sequence and blocked by WP-01 acceptance evidence.


## WP-01 continuation — production error recovery, catalog fail-closed behavior, and visual coverage (2026-10-26)

### Route error/retry recovery

- Feed: added a source-styled **Coba lagi** action connected to `loadFeed(true)`; this retries the canonical authenticated Feed request.
- Explore/Search: added retry actions for search results, trends, and recommendations, each calling its existing canonical API loader.
- Messages: added retry actions for conversation-list load and active conversation load. The handlers reuse the existing authenticated messaging API, not local success simulation.
- Reels: retained the source-styled media-unavailable state and API-load retry button; retry does not invent a playable URL.
- Live: synthetic audio-spectrum and Agent turn-taking timers were removed. The route remains fail-closed until a canonical Live session exists; viewer/like counts and chat identities remain empty.
- AI Cinema and Marketplace: fixed route/component contract mismatches by adding optional canonical catalog props to the existing reference components. Production routes explicitly enable `productionMode`, pass empty catalog arrays and `catalogState="unavailable"`, and do not display the reference repository's demo movies/listings. Purchase, local publish, and local approval simulation remain unavailable in production mode. Existing reference layout classes and component structure are retained.

### Expanded automated evidence

- `apps/web/scripts/visual-smoke.mjs` now covers 22 existing routes at 360×800, 390×844, 820×1000, and 1440×1000; this is 88 route/viewport captures when the workflow completes.
- HTTP responses with status 400 or above now fail the visual route check, in addition to navigation failures and horizontal overflow.
- `apps/web/scripts/smoke-test.mjs` now guards the Feed/Search/Messages retry contracts, production-safe AI Cinema and Marketplace catalogs, and the four required viewport widths.
- Workflow: [Reference UI Validation](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/workflows/reference-ui-validation.yml).

### Configuration reconciliation (source-derived facts)

- Reference `app/globals.css` and target `apps/web/reference-source/app/globals.css` are byte-identical (both only import Tailwind CSS and `tw-animate-css`). Target `apps/web/app/globals.css` contains additional existing application styles; replacing it wholesale would remove required monorepo/auth shell styling, so it is not overwritten blindly.
- Reference `postcss.config.mjs` includes `@tailwindcss/postcss` and `autoprefixer`; target uses Tailwind CSS v4's `@tailwindcss/postcss` plugin. This is a toolchain difference, not an omitted visual component; adding or replacing dependencies without build evidence is deferred.
- Target Next configuration preserves monorepo standalone output and `poweredByHeader: false`; reference-only remote `picsum.photos` allowance is not copied because production UI must not depend on demo avatars.
- Target PWA manifest keeps standalone mode, `start_url` and `scope` at `/`, and the existing `/icon.svg`. The source manifest's `/icon-192.png` and `/icon-512.png` do not exist in the source public tree, so those broken paths are not adopted.

### Remaining WP-01 acceptance blockers

- The source image `public/assets/aistudio/file_00000000e2f48207b9fbf70131d4041f_fb06dd70.png` is still missing from target. The current GitHub connector cannot read the binary body through its UTF-8-only fetch path, so the exact source bytes could not be copied safely in this execution. It remains open; no substitute image was invented.
- Visual screenshots, final Web typecheck/build, and the final visual workflow outcome must be inspected after the latest commit. The previous CI attempt exposed a type contract mismatch in AI Cinema, then catalog prop mismatches in Marketplace and a stale Live simulator setter; fixes are committed, but a later green run is required to prove them.
- UI-COPY-03 remains `in_progress` until the workflow passes, artifacts are confirmed, and the missing source binary is reconciled. WP-02 remains blocked.


## WP-01 final CI evidence checkpoint — 2026-10-26

### Latest accepted automated evidence

- Latest validated commit: `1b29d674c6d94581dcf27255f7bb3337191dd0b7`.
- [Reference UI Validation run](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40219142266) completed successfully. Smoke assertions, TypeScript typecheck, Next.js build, route viewport checks, and artifact upload all passed.
- [Allpha Smoke run](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40219142342) completed successfully, including web-build, native-client-checks, and API tests.
- Final visual artifact: [Download 108 route/viewport screenshots](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40219142266/artifacts/12609106579). Artifact ID `12609106579`, 5,470,357 bytes, retained by GitHub Actions for 14 days from upload.
- The workflow log explicitly reports: `Visual route smoke passed: 27 routes × 4 viewports; screenshots captured for every route.`
- Specific `/workflows` check at 360 px: HTTP 200, viewport width 360, documentWidth 360, bodyWidth 360. No horizontal overflow was reported.

### Modal source-to-target reconciliation

The reference repository contains six modal components and the target contains all six matching filenames under `apps/web/components/reference-ui/`.

- Byte-identical by Git blob SHA: `AskAiModal.tsx`, `CreatePostModal.tsx`, `GenerateModal.tsx`, `TakeoverModal.tsx`.
- Adapted, not byte-identical: `AgentGoalsTasksModal.tsx`, `AgentIdentityModal.tsx`. Both preserve source DOM/class hierarchy and catalog UI while adapting types/imports and preventing false business success. Source active composition check: reference `app/page.tsx` imports/mounts `TakeoverModal`, `AskAiModal`, `GenerateModal`, and `CreatePostModal`; it does **not** import/mount `AgentIdentityModal` or `AgentGoalsTasksModal`. Therefore their absence from the active route is source parity, not a missing source-route interaction. They remain copied, fail-closed components; when an owner phase mounts them, identity must persist only through authenticated `PATCH /v1/agents/{id}` using canonical Agent fields/persona, while goals/task operations require the existing ENG-P10/ENG-P11 runtime/goals contracts. No endpoint, goal registry, or scheduling behavior is invented in UI-COPY-03.
- Feed Story behavior reconciled against the actual source handler (`components/FeedView.tsx`): only Add Story, Live Story, and the `s-3d-world` item have actions. Ordinary non-Live story cards have no viewer callback in the source. This is **source parity**, not an omitted target handler; do not invent a new viewer during UI-COPY-03. A future Stories owner phase may add one only through its canonical route/session contract.

### Scope and phase decision

- The user explicitly excluded searching for or transferring the missing binary asset; it is not a blocker for this checkpoint and no substitute image was created.
- Real/staging testing and deployment were not performed, per product-owner instruction.
- This checkpoint proves automated route smoke, typecheck, build, and screenshot artifact availability for the listed commit. It does not prove external production integrations or every modal action's backend contract.
- WP-01 / UI-COPY-03 should only be marked complete after the two adapted modal contracts and remaining source-to-route interactions are explicitly reconciled. WP-02 remains blocked until then.


## Execution update — UI-COPY-03 modal/story interaction contract (2026-10-26)

- `AgentGoalsTasksModal.tsx` preserves the copied source DOM/Tailwind classes/forms while failing closed when no canonical contract is wired: run-task no longer uses a timer to claim success, task/goal creation and deletion do not write local-only business state, autonomous mode does not toggle only in component state, and goal progress cannot be manually fabricated. Toasts explain the missing canonical Agent Runtime/task/goal contract. No UI redesign was made. Code commits: [de2a2dc](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/de2a2dc16a1271e52f3950eaa52f5f4b8a013209), [653c0e0](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/653c0e0537317bb02e89375623b7aeb6614e1817).
- `AgentIdentityModal.tsx` uses reference catalog/types, but identity/avatar/skills persistence is not represented by the current `/v1/agents` contract. Do not claim this modal is integrated; the current `/agents` page uses its existing API-backed Agent/runtime workflow and does not mount this modal.
- Story strip source behavior: “Tambah” opens Create Post, Live stories open Live Stage, and the source-defined 3D World item opens Spatial World; ordinary non-Live story cards have no source viewer callback in the reference component. Do not invent a story viewer during a copy phase. Canonical story-viewer behavior is a dependency for the owning Stories phase, not a hidden UI redesign.
- The latest 27-route × 4-viewport CI evidence predates these two code commits. This entry does not declare UI-COPY-03 complete. WP-02 remains blocked until UI-COPY-03 acceptance gates are met.


## Final visual/interaction evidence refresh — 2026-10-26

- Reference UI Validation run [#40220755589](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40220755589) passed on commit `04492010275b31530e03f45027af616607a4f18f`: canonical smoke, TypeScript typecheck, Next.js build, Playwright route checks, and screenshot upload all succeeded.
- Visual artifact: [108 route/viewport screenshots](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40220755589/artifacts/12609323883), 5,480,918 bytes, SHA-256 `db5c6eb1a035bd0e3c4b9ab2b2ebdd3f1b150a5cfbbb221be96340ac48cd995a`, expires 2026-11-08. The artifact was downloaded and inspected for `/agents`, `/feed`, and `/workflows` at 360px. These screenshots show the intentional unauthenticated/configuration-required state because public Supabase client configuration is absent in CI; they validate route rendering and viewport framing, **not** authenticated production data parity.
- `/workflows` screenshot at 360px displays the expected configuration fallback and its long configuration keys wrap without horizontal overflow. The workflow's route check passed across 27 routes × 4 viewports (360, 390, 820, 1440).
- Allpha Smoke run [#40220755724](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40220755724) passed API tests, Web tests/build, Native tests/typecheck, and Android Expo export. This is CI evidence only; no staging, production, or physical-device test was run.
- Added source-behavior regression assertions for the Agent Goals/Tasks fail-closed actions and exact Feed Story actions; commit [ac82e42](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/ac82e4201d28f6cf4942f88a68a638b07ad15f9f). Latest CI for this assertion commit must pass before final acceptance.
- Scope classification: the three items raised in the handoff are now reconciled against source truth: Agent identity/task modals are copied but not mounted by the source app composition; ordinary non-Live story cards are deliberately non-interactive in the source. They are not grounds for inventing new UI behavior. Their future authenticated adapters remain owned by the existing Agent identity/runtime and Stories phases.
- Overall UI-COPY-03 remains `IN_PROGRESS` because broader source-to-route parity and the complete design-system/config inventory are not yet proven by authenticated-state screenshots. WP-02 remains blocked.


## Additional style-integrity audit — 2026-10-26

- Exact ordered `className` expression comparison against the current reference source confirms `AgentIdentityModal.tsx`: 74/74 expressions match in order; `AgentGoalsTasksModal.tsx`: 105/105 expressions match in order. The handler/state changes did not change either modal's CSS classes or class order.
- Adapted-component checks show intentional or unresolved class-expression differences: `AiCinemaView.tsx` 340 source vs 341 target expressions (target adds a production empty-catalog state); `MarketplaceView.tsx` 26 vs 27 (empty-catalog state); `AskAiView.tsx` 63 vs 66 (avatar fallback replaces a remote/demo image); `AuthOnboardingFlow.tsx` 134 vs 136 (adds an error-state banner); `LiveExperienceStage.tsx` 94 vs 109. The Live difference is especially material: when `liveStateAvailable=false`, the target currently returns a separate configuration card instead of rendering the reference Live Stage composition with fail-closed data. That branch is **not accepted as exact visual parity** and remains an explicit WP-01 blocker; it must be corrected to retain source composition/styles while presenting no fake session/chat/viewer/slide state.
- CI after the Story contract assertion: [Reference UI Validation #40221302450](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40221302450) succeeded; screenshot artifact [12608938480](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40221302450/artifacts/12608938480) contains 108 route/viewport captures. [Allpha Smoke #40221359534](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40221359534) succeeded for API tests, Web tests/build, Native tests/typecheck, and Android Expo export.
- Do not mark UI-COPY-03 complete yet. The 3 modal/story questions are now accurately reconciled, but the Live fail-closed visual branch and authenticated-state screenshot evidence remain open. WP-02 remains blocked.


## CSS / styling reconciliation audit — 2026-10-26 (latest)

- Compared ordered JSX `className` expressions for all nine adapted reference components against the reference repository. This is a source-level class-expression audit, not a screenshot pixel-diff and not an authenticated-state parity claim.
- Exact ordered class-expression matches: `AgentIdentityModal.tsx` (74/74), `AgentGoalsTasksModal.tsx` (105/105), and `Navbar.tsx` (27/27).
- Components with intentional source-vs-target class-expression deltas that require review against the reason for adaptation: `AiCinemaView.tsx` (340 source / 341 target), `MarketplaceView.tsx` (26 / 27), `AskAiView.tsx` (63 / 66), `AuthOnboardingFlow.tsx` (134 / 136), `LiveExperienceStage.tsx` (94 / 98), and `ProfileView.tsx` (251 / 251 expressions, but ordered expression comparison differs due to changed dynamic conditions).
- Deltas must be classified individually: empty/unavailable/error states and removal of demo content are permitted only when required to prevent fabricated production data; source layout, palette, typography, spacing, and component hierarchy must otherwise remain. Do not delete an explicit error/empty state merely to force a class-count match. No wholesale CSS replacement or redesign is authorized.
- Live Stage CI on commit `3ff5888d98fdab9056e39e1d6b28a3e31013753e` failed the responsive check: `/live` measured document/body width 456 px at 360 px and 390 px viewports; other checked routes passed. Commit `4898e860f7927a34e35ce000526626bc98b9446d` adds responsive wrapping to the existing source header groups without replacing the source composition. Re-run the 27-route × 4-viewport validation before treating this as resolved.
- Route/viewport screenshot CI runs without public Supabase client configuration, so the captured output primarily establishes route HTTP/build/overflow and unauthenticated fallback behavior, not authenticated visual parity. Authenticated visual comparison remains an acceptance gap unless the test environment is safely configured with non-production public test configuration.
- UI-COPY-03 remains `IN_PROGRESS`; WP-02 remains blocked until latest visual CI passes and the outstanding component/style and route parity gaps are accounted for.


## Responsive evidence, CSS delta classification, authenticated parity and Agent task scheduling contract — 2026-10-26

### Responsive CI and screenshot review
- Latest Reference UI Validation run [#40222485728](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40222485728) passed on commit `4898e860f7927a34e35ce000526626bc98b9446d`: smoke assertions, typecheck, Next build, and Playwright route checks for 27 routes × 4 viewports (360, 390, 820, 1440). All routes returned HTTP 200 and no horizontal overflow was reported by the visual smoke script.
- Artifact [12609139769](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40222485728/artifacts/12609139769) contains 108 screenshots, SHA-256 `b273324966402bb38fd66ebf4a511234bb2e01201b478a21f4093ff09cfdd876`, expires 2026-11-08.
- Opened and inspected `live-mobile-360.png`: source Live Stage composition is retained; header wraps without expanding document width; no visible horizontal overflow. Its session/chat/presentation states are unavailable rather than simulated. Automated width checks also passed at 390, 820, and 1440 px. This is CI/browser evidence, not a physical-device test.

### CSS/style delta classification (nine adapted components)
- Exact ordered `className` expressions: `AgentIdentityModal.tsx` 74/74; `AgentGoalsTasksModal.tsx` 105/105; `Navbar.tsx` 27/27.
- `AiCinemaView.tsx` (340 source / 341 target) and `MarketplaceView.tsx` (26 / 27): the additional target expression is an explicit empty-catalog state. Remaining expression-order differences are positional shifts caused by this inserted state, not evidence that all card styles differ.
- `AskAiView.tsx` (63 / 66): the source remote/demo avatar image is replaced by a neutral icon fallback; target also has explicit unavailable/error states. Chat message layout/class expressions remain in the source order after those conditional additions.
- `AuthOnboardingFlow.tsx` (134 / 136): two extra class expressions belong to a visible submission-error banner; source layout styling otherwise remains. This does not by itself prove that the login journey is fully functional.
- `LiveExperienceStage.tsx` (94 / 98): deltas are responsive wrapping on the source header groups and neutral fallback for the unavailable host image/session status. The wrapping change is retained because the exact source header caused measured 456 px document width on 360/390 px. Source composition/card hierarchy remains.
- `ProfileView.tsx` has 251 class expressions in both files; the one semantic difference is source green `Terverifikasi (KYC L2)` changed to neutral `Status belum tersedia` because canonical production response does not establish KYC status. The neutral state must remain; do not claim verification without authoritative data.
- No source card/palette/typography/spacing redesign was made as part of the latest overflow fix. CSS source-level audit does not replace pixel-level comparison against an authenticated reference state.

### Authenticated-state parity gate — still blocked
- The repository now includes `apps/web/scripts/visual-auth-smoke.mjs` and a conditional CI step. It obtains a real Supabase Auth session, verifies FastAPI `/v1/me`, verifies access to the configured owner-owned Agent Studio, captures 5 routes × 4 viewport sizes, checks document/body width, and asserts the schedule panel renders in authenticated Agent Studio.
- The observed CI environment reported `AUTH_E2E_CONFIGURED=false`, so the authenticated capture step was skipped. Existing screenshots still prove unauthenticated fallback/route rendering, not authenticated parity.
- Required protected GitHub Actions secrets: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_API_BASE_URL`, `ALLPHA_E2E_EMAIL`, `ALLPHA_E2E_PASSWORD`, and `ALLPHA_E2E_AGENT_ID`. These must point to a dedicated non-production identity, an Agent owned by that identity, and an isolated API environment. Do not use production account credentials, fabricate sessions, or seed fake business records. Until those inputs exist and screenshots are inspected, authenticated parity remains unproven.

### Task Scheduling implementation — distinct from Goals
- Reference repo `components/AgentGoalsTasksModal.tsx` is UI-only. Its task handlers simulate completion after a timer and seed demo tasks/goals; those behaviors remain excluded from production.
- Task and Goal remain separate: Task is owner-assigned scheduled work; Goal is a strategic objective. The source modal’s Goals tab has not been converted into a schedule or given invented CRUD semantics.
- New source-level implementation exists in `apps/api/supabase/migrations/20261026100000_eng_p11_agent_task_schedules.sql`, `agent_task_schedule_api.py`, `agent_task_schedule_worker.py`, and the `agent_task` Workflow Engine node adapter in `workflow_worker.py`. It adds IANA timezone-aware one-time/daily/weekly schedules, atomically claimed due schedules, per-occurrence idempotency/trace/approval records, pinned Agent/Skill versions, bounded task budgets, owner pause/resume/cancel, and actual runtime/workflow result linkage.
- The schedule worker dispatches through the canonical Workflow Engine; its `agent_task` node creates/executes the durable Agent Runtime task and rechecks ownership, published Skill/version, registered tool/capability policy, approval, idempotency, and budget. Unknown execution outcomes are not marked successful and are not blindly replayed.
- `apps/web/components/reference-ui/AgentTaskSchedulePanel.tsx` is mounted in the existing Agent Studio route. It uses the reference visual vocabulary (dark borders, offset shadows, source palette, compact typography) and sends typed JSON inputs to the registered Tool; it displays backend status, timestamps, traces, and per-occurrence approval.
- Acceptance is **not complete**: the migration is source-only and has not been applied to the canonical database; the scheduler worker entrypoint is registered but remains disabled unless an approved worker service sets `ALLPHA_AGENT_TASK_SCHEDULER_ENABLED=true`. The current canonical `AgentRuntime` executes explicitly registered deterministic tools and the current registry only exposes `text.normalize`; free-form Human Owner instructions are stored as task context but are not interpreted by a general LLM task planner. Do not claim arbitrary autonomous content/social/analytics work until those canonical tool/planner contracts exist.
- Latest API/Web/Native smoke run `40225417989` passed API tests, Web build, and Native checks for its tested commit. The authenticated visual gate still needs the protected E2E secrets above, and full authenticated screenshots have not yet been inspected.
- UI-COPY-03 remains `IN_PROGRESS`; WP-02 remains blocked pending authenticated-state visual evidence and complete route/design-system acceptance.

## Authenticated parity + task-scheduling gate — 2026-10-26
- Latest unauthenticated route/viewport CI passed the horizontal overflow checks at 360, 390, 820 and 1440 px, including the Live Stage correction. It does not prove authenticated-state parity.
- Authenticated screenshot evidence remains blocked pending an explicitly authorized isolated test session/configuration; no user/session is fabricated.
- Task Scheduling is a distinct scheduled-work domain and must not be conflated with strategic Goals. The durable schedule → Workflow Engine → Agent Runtime source slice exists, but the schedule migration is source-only and the worker is disabled by default.
- A duplicate per-run approval route was removed; the single route records approval for that occurrence only and preserves the schedule's future approval setting. Regression assertion added; wait for the new CI run before marking the fix validated.
- The current Tool Registry only has text.normalize. Natural-language instructions are currently stored as schedule metadata and are not executed by a general LLM planner. Domain task types without registered canonical tools fail closed. Full autonomous task execution is therefore not accepted yet.
- AgentTaskSchedulePanel.tsx is a target-only component, not a direct source-repository component; exact source style reconciliation is still required before UI-COPY-03 can close.

---

## Source/target inventory refresh — 2026-10-26 (UI-COPY-03 remains open)

**Pinned source:** `urbanrealty36-ops/Allpha-Front-End-UI-New@aad317c1f651163f065cd42b9ae35267d18f354a`  
**Target branch:** `work/ui-copy-03-eng-p11-input-contract-20261026`; inventory commit before this refresh was `cbf3c3b105a10e623b9a1e1905fef921f6113d2d`. The CSS isolation follow-up is commit `b812e94793b2966d9f78243aecccffe382088b87`.

### Component manifest result

- Reference tree contains **25** `components/*.tsx` source components.
- All **25/25** have a corresponding file under `apps/web/components/reference-ui/`; there are no missing source component files.
- **11/25** are byte-identical by Git blob SHA: `AskAiModal`, `BottomNav`, `CreatePostModal`, `GenerateModal`, `PostDetailView`, `SkillsChallengeHub`, `TakeoverControlView`, `TakeoverModal`, `ThreeWorldView`, `Universe3DExperience`, `Universe3DHubView`.
- **14/25** are production adapters, not byte-identical: `AgentGoalsTasksModal`, `AgentIdentityModal`, `AiCinemaView`, `AllphaHubView`, `AskAiView`, `AuthOnboardingFlow`, `ExploreView`, `FeedView`, `LiveExperienceStage`, `MarketplaceView`, `MessagesView`, `Navbar`, `ProfileView`, `ReelsView`. Each delta still requires preserving the source JSX/layout/class hierarchy while changing only data/action boundaries and unavailable states needed to prevent demo behavior.
- Five target-only components are present: `AgentTaskSchedulePanel`, `AuthOnboardingRoute`, `ReferenceApp`, `ReferenceFeedChrome`, and `ReferenceNavigation`. The first is a target-only scheduler UI, not a component in the reference repo; keep its lifecycle/API ownership in the canonical ENG-P11 phase and do not treat its visual similarity as source-copy parity. The remaining integration-shell files are target routing adapters, not reference components.
- The reference's `app/page.tsx` is a single-page composition; the target exposes 27 Next route pages. Component-file presence is not proof that every source view is mounted at the right route or that all source affordances work. Route-to-component and interaction acceptance remains a separate gate.

### CSS, framework and PWA

- Reference `app/globals.css` is 49 bytes and imports Tailwind plus `tw-animate-css`. Target `apps/web/app/globals.css` includes the reference imports plus legacy identity and owning-domain styles; replacing it wholesale would break unrelated domain routes and is not approved.
- The target CSS had unscoped generic rules for anchors, form controls, buttons, label-small text, and smooth scrolling. These were narrowed to `.identity-shell` / `html:has(.identity-shell)` so legacy identity-page styles do not cascade over the copied reference routes. Change commit: `b812e94793b2966d9f78243aecccffe382088b87`. This is a CSS-isolation correction, not visual acceptance; dynamic selectors and browser cascade still need evidence.
- The target PWA manifest uses the existing `/icon.svg`. The reference manifest names `/icon-192.png` and `/icon-512.png`, but those files are absent from the reference public tree. Do not copy broken manifest paths or invent replacement PNGs.
- Exact public-tree audit: reference `public/` has 21 files; target `apps/web/public/` has 20. Twenty paths match by path and blob SHA. One unmatched file is `assets/aistudio/file_00000000e2f48207b9fbf70131d4041f_fb06dd70.png` (2,030,869 bytes, source blob `ad78971cbe154e01325dc90f8ca0c88349c35c2b`). A source code search found no reference to this filename; it is in the Aistudio attachment/evidence folder rather than a referenced runtime UI asset. The GitHub connector cannot decode this binary blob as UTF-8, so it was not falsely reported as copied. If this evidence attachment is required in the deployed public tree, it still needs an approved binary-transfer path and exact checksum verification.
- Source `package.json` and monorepo `apps/web/package.json` intentionally differ in scripts and framework patch versions. Target adds tests, typecheck and Supabase integration, while source includes source-only dependencies/configuration. Do not replace the monorepo package/config wholesale; continue checking Tailwind/PostCSS and imported source classes against the existing workspace setup.

### Interaction contract disposition

- Ask AI: source calls a demo `/api/agent/interact` and has simulated fallback/reward behavior. Target must retain the source composition but not send to that demo route or invent a chat-turn endpoint. The inspected target route has no `onSubmitQuery` callback; until the owning canonical contract is available, the UI must present a truthful unavailable state and must not claim delivery/reply/credit settlement.
- Stories: the source Feed only binds add-story, Live Stage and its spatial item; ordinary story cards have no viewer handler. Keep source behavior exactly—do not invent a Story Viewer click contract.
- Agent Goals/Tasks: source component is not mounted in the source root composition, and its generic form does not match the current runtime's owned-session + published-skill + declared-tool + idempotency contract. Do not invent Goal CRUD or task success in this copy phase.
- AI Cinema and Marketplace: source layouts remain present, but catalog, purchase, billing, moderation and credit operations are not inferred from demo fixtures. Target routes fail closed with unavailable/empty data until their existing owner phases provide canonical contracts.

### Evidence and gate

- A previous automated CI artifact recorded 108 screenshots for 27 routes × widths 360, 390, 820 and 1440 on commit `4898e860f7927a34e35ce000526626bc98b9446d`. It is **stale for acceptance** because later UI code changes are not represented in that artifact. The authenticated visual gate was also skipped because protected Supabase/API test-session configuration was not present.
- Allpha Smoke, ENG-P22 and ENG-P23 succeeded on the documentation-only predecessor commit `cbf3c3b105a10e623b9a1e1905fef921f6113d2d`; Vercel statuses reported `build-rate-limit`, and ENG-P01 was still running. These results do not certify the UI after the CSS isolation commit.
- Do not close UI-COPY-03 from the component manifest alone. Current blockers: refreshed route/viewport screenshot evidence for the latest code, authenticated-state evidence with an approved isolated test identity, source-to-route composition review, and interaction-contract dispositions for all source controls. WP-02 remains blocked until the acceptance gate is actually satisfied.

### Correction — latest public asset transfer verified (2026-10-26)

The current-head Aistudio attachment previously listed as missing was subsequently captured from the pinned reference source by GitHub Actions and committed on the working branch. The binary is:

- `apps/web/public/assets/aistudio/file_00000000e2f48207b9fbf70131d4041f_fb06dd70.png`
- Bytes: `2,030,869`
- Source Git blob SHA-1: `ad78971cbe154e01325dc90f8ca0c88349c35c2b`
- SHA-256: `fb06dd700425e620f8a26d28af76ae40f8da5a76b70aa7cb1bffb1e688899473`
- Capture workflow run: [40278061361](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40278061361) — success; its log confirms size and Git blob SHA verification.

A fresh Git-tree comparison against source `aad317c1f651163f065cd42b9ae35267d18f354a` now finds **21/21 public files match by path and Git blob SHA**. The capture workflow manifest was restored after an intermediate automation formatting defect and is now complete; its row-level hashes and temporary-media inventory remain intact. The capture workflow's row-boundary handling was corrected in commit `11cf1c8705de8182834c723d5a9da6fa377c73f5`.

This closes the public asset path/hash inventory gap. It does not by itself close UI-COPY-03: route wiring, authenticated state, interaction contract gaps, and visual acceptance remain separate gates.
