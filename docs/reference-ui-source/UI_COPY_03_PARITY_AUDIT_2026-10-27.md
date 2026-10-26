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
