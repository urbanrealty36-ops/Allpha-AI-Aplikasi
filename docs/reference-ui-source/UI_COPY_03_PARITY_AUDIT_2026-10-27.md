# UI-COPY-03 — Reference UI parity audit

Audit date: 2026-10-27
Canonical repository: https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi
Reference repository: https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New
Reference branch: `main`
Reference commit: `b6c9fc728d5d031a28b22fbbec9a546846900e87`
Snapshot manifest: `docs/reference-ui-source/REFERENCE_SOURCE_SNAPSHOT_MANIFEST.json`

## Verified snapshot result

- GitHub Actions run [40374011039](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/40374011039) completed successfully.
- The source snapshot manifest reports 120 tracked source files copied and verified against Git blob SHA-1 and records per-file SHA-256.
- Inventory: 37 TSX components, 1 CSS file in the reference source tree, and 49 public/image asset paths. The reference `app/globals.css` contains only Tailwind and `tw-animate-css` imports; most component presentation is implemented in component-level classes/markup.
- Snapshot is archived under `docs/reference-ui-source/Allpha-Front-End-UI-New-SNAPSHOT/`. Public assets and the source stylesheet are mirrored separately.
- This is source-snapshot verification, not proof of production route parity or feature completion.

## Runtime integration findings

The canonical app already has route adapters and many source-styled components. Preserve those adapters; do not replace them with the reference app orchestrator or its demo store.

| Area | Current evidence | Required next action |
|---|---|---|
| Authentication/onboarding | `/login` mounts `AuthOnboardingRoute`, which uses the reference-styled `AuthOnboardingFlow` and canonical Supabase/API completion logic. The full `AuthOnboardingPage` source is archived and present separately. | Compare the full-page onboarding flow against requested slides/register wizard and integrate only through canonical auth/profile/agent APIs. Do not grant demo bonus credits. |
| Feed/stories | `/feed` uses a canonical API adapter and source `FeedView`; phase plan documents missing canonical individual story viewer route/callback. | Preserve source visual components; wire story viewing/reactions/replies only when backed by API contracts. |
| Notifications | `/notifications` has a canonical authenticated API adapter. | Align source categories/actions while retaining API-defined category/payload semantics and no fabricated credit/royalty amounts. |
| Marketplace | `/marketplace` mounts source `MarketplaceView` with an empty unavailable catalog and purchases disabled because canonical listing/booth/purchase contract is missing. | Keep source layout; implement API contract before enabling listings, shipping quotes, payments, receipts, or purchase success. |
| AI Cinema | `/ai-cinema` mounts source `AiCinemaView` with no fabricated catalog and production mode enabled. | Preserve source layout; do not show fake view counts, ratings, royalty ledger, publish/approval, or billing outcomes. |
| Profile/settings | `/profile` loads human and agent identity from canonical API. | Connect settings, passport, creator tools, financials and credits to real contracts; never display static analytics/royalty balances as live facts. |
| Spatial/3D | Canonical web has spatial route and canonical renderer; source `menggu3dEngine.ts` and source `Universe3DHubView.tsx` differ from current adapted runtime versions. The reference commit adds GLB export/download features that are not fully mirrored in the runtime hub. | Port the source visual/GLB functionality in a controlled merge, using approved/published asset manifests and canonical APIs; do not replace route/auth boundaries or claim unverified assets are published. |
| Live Experience / product attachments | Source components exist and canonical routes/adapters exist in the repo. | Reconcile document upload, attached product catalog, direct checkout and live chat with actual backend endpoints; no local simulated success. |
| Android/iOS | `apps/client` is React Native + Expo and has its own native spatial renderer/navigation/theme catalog. | Keep native architecture; port UX patterns into native screens rather than importing web React components. |

## Non-negotiable production boundaries

- No demo balances, transactions, credits, bonus claims, ratings, views, seller payouts, royalties, fake online counts, or payment success become production data.
- Do not bypass FastAPI, Supabase Auth, authorization, RLS, moderation, approved spatial manifests, or billing contracts.
- Keep the reference UI's spacing, typography, colors, cards, buttons, modal layout, responsive behavior, and asset appearance; change only data wiring and required accessibility/security behavior.
- No staging or real-world checkout tests are requested. Code-level implementation can proceed without staging, but no claim of production verification should be made without evidence.

## Acceptance gate

UI-COPY-03 remains IN_PROGRESS until every source component/route/style/asset is inventoried, each requested feature is mapped to a runtime route/component and canonical API, source-to-runtime visual differences are accounted for, and missing backend contracts are documented as explicit blocked states. Snapshot success alone does not pass this gate.


## Follow-up implementation update (2026-10-27)

- Byte-for-byte synchronized the following reference components into the runtime component directory, using the source repo's current `main` blobs:
  - `components/Universe3DHubView.tsx` source blob `850b0819e4c6d84fb79dc10d37b8ab7b80f6df2d` → `apps/web/components/reference-ui/Universe3DHubView.tsx`; target commit `fb89c9a1bf4a1f48873c05672cdccbd97101d44d`.
  - `components/Universe3DExperience.tsx` source blob `904518182a463c6edc3e892b5575140be9958722` → `apps/web/components/reference-ui/Universe3DExperience.tsx`; target commit `6aae2c306c21585d0ec871926bae1b29782ea07a`.
- The newer Universe hub source imports the already synchronized `Menggu3DUniverseGallery`, `Menggu3DViewerModal`, and `menggu3dEngine`; its export/download affordances and GLB generation are now present in the runtime source component.
- This sync is an exact source-code copy, not a runtime route acceptance result. The current canonical `/spatial/navigation` route still uses `SpatialNavigationBrowser` and canonical spatial manifests, not the demo-driven reference Universe hub. It must be connected without using the reference's hardcoded world metrics, local-only state, or simulated credit/reward callbacks as production truth.
- No design changes were made to the copied components. No staging or real-world payment tests were run.
- `WP-01 / UI-COPY-03` remains `IN_PROGRESS`: route integration, API wiring, complete feature/component parity, and the requested no-demo-data acceptance still require implementation and evidence.


## Public splash/onboarding route implementation (2026-10-27)

- Added `apps/web/app/welcome/page.tsx`, mounting the source `AuthOnboardingPage` component for the first-visit splash slides and ecosystem introduction.
- Changed `apps/web/app/page.tsx` to redirect `/` to `/welcome`; the public home/feed is no longer the initial root route.
- Updated `ReferenceAppShell` to hide authenticated app navigation on `/welcome`, preserving the source page's full-screen layout.
- Production action handling: Google/register/login actions in this page hand off to canonical `/login` instead of treating demo form data as a real session; the canonical login route uses Supabase Auth and the FastAPI provisioning adapter. The "Buka Feed" / guest path remains available as the source UI specifies.
- The welcome route passes empty identity values, not `INITIAL_USER` / `INITIAL_AGENT`; it does not grant the source's +50 AI Credits claim. The original source visual styling is retained; only production event wiring is adapted.
- Commits: `10c03589ef260737449ceb505fb6c426c6e9f00a` (safe auth handoff), `3dfaf1dfff00b8a535c55aa98a3438f6e9b80ea0` (welcome route), `2a0cbe8d2157a8230a8c8ccdcab8fbc19f8971f9` (root redirect), `5e833bf5375d0064eaab0a933664fc680f8c39d8` (hide app nav on splash).
- No staging/browser/real payment testing was performed, as requested. Route code was committed, but visual/runtime acceptance is not claimed.


## Public homepage workflow clarification (2026-10-27)

- Product rule confirmed: users must see the reference Splash/Welcome page first, then may enter the public homepage/feed without signing in. Login is required only for protected actions/flows according to existing route/API authorization rules.
- Current implementation: `/` redirects to `/welcome`; the source CTA "Buka Feed Aplikasi" / guest bypass routes to `/feed`; `/feed` loads the canonical feed API and does not require the UI onboarding form to be completed first. Mutating/identity-dependent actions remain subject to canonical authentication and API authorization.
- No login wall was added to the public feed. The Welcome page's login/register buttons route to `/login` and canonical Supabase/FastAPI auth flow.
- No fake demo identity, simulated authentication, credits bonus, or transaction is persisted by the welcome route.
- Remaining acceptance work: inventory every source file and map each screen/modal/action/style/asset to runtime routes, reconcile API-backed actions and verify responsive UI parity. No staging or live transaction test was run.


## Source freshness re-check and verified reference HEAD (2026-10-27, multi-method)

The previous freshness statement must be interpreted carefully: this check queried GitHub repository metadata, the REST branches endpoint, the REST commits endpoint, GitHub commit search sorted by committer date, and the recursive Git tree. All methods identify `main` at `b6c9fc728d5d031a28b22fbbec9a546846900e87`, committed/pushed 2026-10-26 17:03:27Z. Repository metadata reports `pushed_at=2026-10-26T17:03:27Z`; the only listed branch is `main`. Thus the source is not stale relative to that latest remote commit, but the canonical repo's archived source snapshot does not fully match that HEAD and must be refreshed for changed files.

Verified latest source tree:
- Tree SHA: `b6c9fc728d5d031a28b22fbbec9a546846900e87`
- Recursive tree: not truncated; 148 entries including directories, 120 tracked file blobs.
- Latest commit: [b6c9fc728d5d031a28b22fbbec9a546846900e87](https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New/commit/b6c9fc728d5d031a28b22fbbec9a546846900e87)
- Message: GLB export and studio tools in 3D engine, dynamic model loading in `Menggu3DViewerModal`, download capabilities in `Universe3DHubView`/gallery, and billboard customization.

Fresh hash checks against current canonical runtime confirm these exact source matches:
- `components/Menggu3DUniverseGallery.tsx` -> `apps/web/components/reference-ui/Menggu3DUniverseGallery.tsx` (SHA `28ab5f90acbc71fd06a02390b8390005bfe362ee`)
- `components/Menggu3DViewerModal.tsx` -> `apps/web/components/reference-ui/Menggu3DViewerModal.tsx` (SHA `5a2b8ddfb1aa266ed65f65a368ef7326ed85e63b`)
- `components/Universe3DExperience.tsx` -> `apps/web/components/reference-ui/Universe3DExperience.tsx` (SHA `904518182a463c6edc3e892b5575140be9958722`)
- `components/Universe3DHubView.tsx` -> `apps/web/components/reference-ui/Universe3DHubView.tsx` (SHA `850b0819e4c6d84fb79dc10d37b8ab7b80f6df2d`)
- `lib/menggu3dEngine.ts` -> `apps/web/lib/menggu3dEngine.ts` (SHA `d77482123c22c17d078b35e434b5db17190b4c25`)
- `hooks/usePWAInstall.ts` -> `apps/web/hooks/usePWAInstall.ts` (SHA `5830140e95b10d57f07a0c434d407317175aa8eb`)

Important non-identical files still requiring component-by-component review include `AllphaHubView.tsx`, `AuthOnboardingFlow.tsx`, `BottomNav.tsx`, `CreatePostModal.tsx`, `LiveExperienceStage.tsx`, `MarketplaceView.tsx`, `Navbar.tsx`, and `ProfileView.tsx`. Their runtime copies contain production wiring or omit portions of source content; do not replace wholesale until source-only demo state is isolated from canonical auth/API/persistence. This is a UI-preserving adapter task, not permission to redesign the source.

This section supersedes any inference that the source repository was not updated. It does not mark UI-COPY-03 complete. No build, typecheck, browser/viewport, staging, or device test is claimed.


### UI-COPY-03 — first high-impact component sync slice (2026-10-27)

- Synced `apps/web/components/reference-ui/BottomNav.tsx` byte-for-byte from reference `components/BottomNav.tsx`; resulting blob SHA exactly matches source `c2841cf7048bd2130f8634435d683523e04325d6`. Commit: `8c160e506decf177be392ddd2217fcca937a6e84`. This restores the source `ONBOARDING_PAGE` tab type and hides the bottom navigation for the full-page onboarding state without changing CSS or visual markup.
- Per-file content comparison completed for AllphaHubView, FeedView, CreatePostModal, LiveExperienceStage, MarketplaceView, ProfileView, Navbar, and BottomNav. It shows significant source-only UI/features in the first six components, especially CreatePostModal (source 844 lines vs runtime 553), LiveExperienceStage (898 vs 422), MarketplaceView (820 vs 217), and ProfileView (1488 vs 1005). This is substantive missing source UI, not merely formatting drift.
- Safety finding: the source components also contain demo fixtures and simulated business states (for example hard-coded creator/agent balances, sample marketplace inventory, transaction/settlement records, sample social stories/posts, viewer/like counts, and purchase flows). A wholesale copy into runtime would violate the explicit production-data constraint. The next change must preserve source JSX/classes/sections while binding data/actions to canonical API adapters and rendering honest empty/loading/error states. Do not claim full parity based on the BottomNav copy alone.
- Current component diffs and source/target SHA evidence were checked directly against current reference `main` HEAD `b6c9fc728d5d031a28b22fbbec9a546846900e87`. No build/typecheck/browser/viewport/device tests were run.
- UI-COPY-03 remains `in_progress`; remaining work includes source-UI restoration for AllphaHub, Feed/CreatePost, LiveExperience, Marketplace, Profile and Navbar while retaining production adapters; then exact source-to-runtime mapping for remaining files/assets/PWA config.


### UI-COPY-03 — Navbar source structure restoration (2026-10-27)

- Restored the reference `components/Navbar.tsx` markup and source class structure into `apps/web/components/reference-ui/Navbar.tsx`, retaining the runtime search submit callback and nullable production credit values.
- Preserved source buttons and callbacks for the Store & Booth action and onboarding-page navigation; these controls only appear when their existing optional callbacks are supplied by the app shell.
- Removed the source's fallback display of 730 credits and its default unread-message count of 2 from runtime behavior; unavailable credit values remain `—` and unread badges require a real numeric value.
- Source file SHA: `fab9a740d3a7a8d81e7219be27f01b9d67ca8261`. Runtime Navbar commit: `8291e7d8dd20f401608f78e0b89faad0f3fc5ed5`.
- This is a partial parity slice only. The app shell callback wiring and the remaining major source components still need reconciliation. No build, typecheck, browser, viewport, staging, or device tests were run. UI-COPY-03 remains `in_progress`.


### UI-COPY-03 — Allpha Hub Marketplace restoration and onboarding Menggu image (2026-10-27)

- Restored the reference `MARKETPLACE` tab in `apps/web/components/reference-ui/AllphaHubView.tsx`, including the source Marketplace & Booth 3D hero, quick-guarantee chips, Booth directory card layout, featured product card layout, and the original source utility classes/styles.
- Reconnected optional `onOpenMarketplace` and `onOpenStoreAndBoothModal` callbacks to the source buttons. In `productionMode`, the hard-coded demo booth/product arrays are suppressed and honest empty states are shown; no demo booth visitors, product counts, sample products, or purchase results are rendered.
- AllphaHub runtime commit: `14cd509000ce3d739f043881436fe9c754f2036d`.
- Updated the onboarding welcome slide image reference to the source's existing 3D Menggu asset `/assets/slides/slide_welcome_3d_1793022854882.jpg` without changing the surrounding markup, CSS, colors, fonts, or layout. Commit: `4ca6a06faf74d1cad70a911472f0302a229b88ea`.
- Verified the SHA-1 Git blob hashes of `public/assets/slides/slide_welcome_3d_1793022854882.jpg` and all five `public/assets/menggu3d/*.jpg` files match the reference repository exactly. These assets were already present in the target PWA public directory; they were not replaced or duplicated.
- The remaining `CreatePostModal`, `LiveExperienceStage`, `MarketplaceView`, `ProfileView`, and `FeedView` work remains. UI-COPY-03 remains `in_progress`. No build, typecheck, browser, viewport, staging, or device tests were run.
