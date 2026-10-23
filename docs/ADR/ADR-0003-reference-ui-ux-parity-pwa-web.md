# ADR-0003: Reference UI/UX Parity and PWA Web Delivery

- **Status:** Accepted by Product Owner
- **Date:** 2026-10-23
- **Decision owner:** Product Owner
- **Scope:** Web client delivery mode and UI/UX refactoring using `urbanrealty36-ops/Allpha-Front-End-UI-New` as the visual/interaction reference.

## Context

The Master PRD v3.0 states that PWA is not a target product or architecture component. The Product Owner has now explicitly directed that the canonical Allpha Web client be refactored to match the reference repository's full UI/UX and delivered as a PWA, while the Native Client remains a React Native + Expo Android/iOS application. The Product Owner confirmed this exception on 2026-10-23.

The reference journey must remain: Splash → Human Register/Login → AI Agent Identity Onboarding/Register → FeedView as the main page. The 3D Universe is a navigable hub, not the main landing page. UI layout, CSS, visual styling, components, routes/navigation semantics, bottom navigation, navbar, page composition and user workflows are to be preserved from the reference; local/mock data must be replaced with canonical backend integrations.

## Decision

1. **Narrowly amend the PRD's PWA exclusion:** `apps/web` may be delivered as an installable Progressive Web App. This exception applies only to the Web client and does not change the Native Client requirement or create a separate application/repository.
2. Keep the canonical monorepo topology: `apps/web`, `apps/client` (Expo Android/iOS), `apps/super-admin`, and `apps/api` (FastAPI). Do not add a second backend or duplicate domain engines.
3. Treat `urbanrealty36-ops/Allpha-Front-End-UI-New` as the source of truth for the requested reference UI/UX. Preserve its visual and interaction contract; adapt only platform-specific implementation details needed for native components/accessibility/responsiveness without redesigning the experience.
4. Both Web and Native must expose equivalent journeys, domain capabilities, navigation semantics and states, using the same typed/versioned FastAPI API contracts and canonical domain services. Component implementations may differ where required by web/native platform constraints.
5. The canonical journey is Splash → Human Register/Login → AI Agent Identity Onboarding/Register → FeedView. FeedView is the post-onboarding home. Universe 3D is a hub reached through navigation, never the default home.
6. Remove local/mock/fake business data and simulated success from production flows. All business reads/writes must use the canonical FastAPI path and Supabase source of truth. Client-side Supabase Auth/session operations are permitted where already specified; clients must not bypass FastAPI for business operations. All LLM/model execution must use the canonical AI Gateway/Model Router.
7. Do not invent additional engineering phase numbers. Reconcile work and status into the existing ENG-P00–ENG-P37 fixed phase plan and owning phases. Add missing domain implementation to its canonical owner phase and preserve dependencies.
8. Keep PWA installability distinct from offline business functionality. Do not claim offline support unless service-worker caching, mutation queuing, conflict handling, and tests are implemented and verified.

## Consequences

- The Master PRD's blanket PWA exclusion is overridden only for `apps/web` by this accepted, narrow ADR. Other PRD requirements remain in force.
- Web may include a web manifest, installability support and an appropriately scoped service worker when required by the reference app. It remains a web client, not a replacement for Expo Native.
- Reference UI/UX parity must be validated against actual source/screens and relevant viewports; Native parity requires Android/iOS visual and interaction checks.
- UI parity does not constitute backend integration or feature acceptance. Each journey requires evidence for API contracts, backend service/engine, canonical data path, authorization, loading/empty/error/retry states and relevant tests.
- The Product Owner has authorized this decision; no further approval is required to implement within this scope.

## Acceptance criteria

- Web PWA and Native Expo clients follow the canonical onboarding-to-FeedView journey.
- FeedView is the default authenticated home; Universe 3D is a secondary hub.
- Reference UI/UX is preserved without intentional redesign.
- Production paths contain no mock business data or fake success responses.
- Both clients use canonical FastAPI contracts for business operations and canonical engines/data.
- Missing endpoints, engines or migrations are implemented within their owning existing phase; no parallel phase numbering is introduced.
- Build/source checks are reported accurately; full real-environment acceptance remains unverified until actually exercised.
