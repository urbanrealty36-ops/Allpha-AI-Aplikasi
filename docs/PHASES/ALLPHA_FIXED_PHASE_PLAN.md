# ALLPHA FIXED PHASE PLAN
**Status:** Canonical engineering execution plan  
**Applies to:** `main` · Monorepo: `Allpha-AI-Aplikasi`  
**Last reconciled:** 2026-10-13  
**Authority:** Master PRD v3.0.0 remains the product source of truth. This document is the single operational source for engineering phase order, phase status, repo coverage, and next action.

## 1. Rules that prevent phase drift
1. Do not create a parallel roadmap, phase namespace, or new phase to compensate for missed implementation.
2. Product phases remain `PRD-P00–PRD-P24` as defined by the Master PRD. Engineering execution phases remain `ENG-P00–ENG-P37`. Keep these namespaces distinct.
3. This is the only operational phase plan. Update this file when status or the next phase changes; do not create a separate status board, crosswalk, traceability matrix, or repeated phase report.
4. A phase is not complete because documentation, a workflow, a build, or one app passed. It must deliver the promised user journey across every affected repo.
5. Every feature must be mapped to the four app surfaces before implementation. Mark each repo `change`, `integrate`, or `not affected (reason)`; a blank row is not allowed.
6. Work directly on `main`, as requested by the Product Owner. Keep commits focused. Run only relevant automated checks, fix failures, and continue; no redundant manual approval ceremonies.
7. Do not claim device, integration, or production verification unless it was actually run and evidence exists.
8. Keep Master PRD, this plan, `AGENTS.md`, source code, tests, migrations, and necessary environment/security documentation. Remove duplicated phase-planning/status documents rather than keeping multiple competing sources.

## 2. The four-repo execution contract
The four applications live in one monorepo. Every phase starts with a quick impact map and ends with a repo-by-repo delivery summary.

| Repo | Owns | Required checks when changed |
|---|---|---|
| `apps/web` | Next.js web client | lint/build and relevant UI journey |
| `apps/api` | FastAPI, canonical domain/API behavior, authorization, migrations | pytest, API/contract tests, migration checks when applicable |
| `apps/client` | Native Android and iOS end-user application | native project/build configuration, Android build/test and iOS build/test where toolchain permits; report unavailable platform verification honestly |
| `apps/super-admin` | Separate privileged operator console | build/lint plus permission and privileged-journey tests |

### Required per-phase checklist
- [ ] **Web:** list the files changed or explain why the phase does not affect Web.
- [ ] **API/DB:** list the files/migrations changed or explain why the phase does not affect API/DB.
- [ ] **Native Client:** list the Android/iOS files changed or explain why the phase does not affect native UX.
- [ ] **Super Admin:** list the files changed or explain why operator workflows are unaffected.
- [ ] **Cross-app contract:** ensure clients use typed API contracts and never perform privileged business writes directly.
- [ ] **Automated checks:** run relevant checks and fix failures before moving on.
- [ ] **Truthful status:** update this document with implementation status, test results, remaining blocker, and next phase.

“Not affected” must include a brief concrete reason (e.g. “public profile field-only API fix; no operator workflow or native screen changes”). “Not affected” cannot be used merely because that repo was overlooked.

### Definition of a useful vertical slice
For a user-facing feature, complete all affected parts together: UI states (loading/empty/success/error/retry), API, persistence where required, authorization/privacy, and basic observability. Use one shared backend/domain truth. Do not make a UI mock and call it implemented. For native work, a README or empty directory does not count as a client implementation.

## 3. Canonical phase order and current status
Statuses use the Master PRD vocabulary: `not_started`, `in_progress`, `blocked`, `implemented`, `integration_verified`, `acceptance_passed`, `production_verified`. Status is intentionally conservative; only evidence actually observed is recorded.

| Phase | Fixed scope | Current status | Next implementation focus |
|---|---|---|---|
| ENG-P00 | Product contract and minimal delivery governance | in_progress | Keep governance lightweight; this file is the single operational phase plan |
| ENG-P01 | Platform foundation and deployable thin slice across all four repos | in_progress | **Close the missed native deliverable:** bootstrap real Android/iOS app in `apps/client`, establish buildable native projects, navigation/design foundation, API configuration, and a working first screen. Verify the existing Web/API foundation without repeating completed work |
| ENG-P02 | Database, authentication, authorization and tenant isolation | in_progress | Continue from existing Supabase-backed code; finish real auth and cross-tenant integration checks, no new database |
| ENG-P03 | Human identity, profile, settings and privacy | in_progress | Reuse existing API/Web implementation; integrate native profile/session flow and close only actual gaps |
| ENG-P04 | Social Graph | not_started / not_verified | Implement canonical Social Graph scope; do not confuse it with the historical Agent Identity package |
| ENG-P05 | AI Agent identity, ownership, persona and passport | in_progress (existing work mapped here) | Preserve existing Agent Identity code/docs in git history/source; reconcile identifier without rebuilding it as Social Graph |
| ENG-P06 | Agent Studio, skills, tools and capability governance | not_started | Implement after required identity foundations |
| ENG-P07 | Knowledge ingestion, document processing and Agent learning | not_started | Follow dependency order in Master Plan |
| ENG-P08 | Agent memory, retrieval, context assembly and privacy isolation | not_started | Follow dependency order in Master Plan |
| ENG-P09 | AI Gateway, Model Router, provider adapters and cost policy | not_started | Follow dependency order in Master Plan |
| ENG-P10 | Agent runtime, tool execution and conversation sessions | not_started | Follow dependency order in Master Plan |
| ENG-P11 | Durable workflow orchestration, checkpoint and resume | not_started | Follow dependency order in Master Plan |
| ENG-P12 | Skill Challenge, Agent evaluation, achievements and rewards | not_started | Follow dependency order in Master Plan |
| ENG-P13 | Content creation | not_started | Build vertical slices across affected clients/API |
| ENG-P14 | Feed | not_started | Build vertical slices across affected clients/API |
| ENG-P15 | Reels and media | not_started | Include media upload/playback and failure states |
| ENG-P16 | Stories and moments | not_started | Include media lifecycle and privacy |
| ENG-P17 | Search and discovery | not_started | Include query/API/UI and privacy |
| ENG-P18 | Messaging | not_started | Include realtime and delivery/error behavior as specified |
| ENG-P19 | Communities and collaboration | not_started | Include membership and authorization |
| ENG-P20 | Notifications | not_started | Include native push integration when configured |
| ENG-P21 | Spatial domain and navigation | not_started | Shared spatial contracts for Web and native |
| ENG-P22 | Theme and asset pipeline | not_started | Use canonical asset catalog and real assets |
| ENG-P23 | World renderer and booths | not_started | Verify renderer on supported Web/native surfaces |
| ENG-P24 | AI Character and animation | not_started | Reuse canonical character/animation contracts |
| ENG-P25 | Live Experience | not_started | Include client, API and operator impacts |
| ENG-P26 | Realtime Streaming | not_started | Verify supported device/runtime paths |
| ENG-P27 | Events and scheduling | not_started | Cross-app journey |
| ENG-P28 | Agent Marketplace | not_started | Cross-app journey |
| ENG-P29 | Commerce and creator economy | not_started | Server-authoritative transactions |
| ENG-P30 | Subscription, credits and billing | not_started | Payment provider integration, idempotency and reconciliation |
| ENG-P31 | Advertising and sponsorship | not_started | Consent, delivery and measurement |
| ENG-P32 | Trust, safety and moderation | not_started | Cross-cutting enforcement and user/operator journeys |
| ENG-P33 | Analytics and user insights | not_started | Privacy-aware instrumentation |
| ENG-P34 | Admin Control Plane | not_started | Implement in `apps/super-admin` plus authorized API paths |
| ENG-P35 | Developer platform and interoperability | not_started | API contracts and credentials governance |
| ENG-P36 | Observability and AI evaluation | not_started | Cross-cutting metrics, logs and evaluation |
| ENG-P37 | Final E2E, regression and release gate | not_started | Final integration/release verification only; do not defer feature implementation here |

**Important status note:** The table is a reconciled working baseline, not a claim that all unreviewed phases have been audited. Existing ENG-P02/P03 and Agent Identity work is not erased. ENG-P04 is Social Graph in the canonical engineering plan; the existing document/code package titled ENG-P04 Agent Identity must not be silently overwritten or reimplemented. Treat that work as ENG-P05 for future roadmap references, while retaining its implementation.

## 4. Immediate execution order
1. **ENG-P01 native foundation gap:** create actual Android/iOS source projects under `apps/client`; select a shared native stack only after checking repo dependencies and PRD constraints. Deliver an app launchable in emulator/device, navigation shell, API base configuration, session boundary, and clear loading/error states. Do not spend another phase on planning documents.
2. **ENG-P02/P03 integration closure:** test existing backend/Auth/profile work against the real configured Supabase environment and integrate native login/profile. Do not duplicate Web work.
3. **ENG-P04 Social Graph:** implement canonical phase scope in API plus affected Web, Client and Super Admin surfaces.
4. **ENG-P05 Agent Identity:** continue from existing implementation; close remaining integration evidence without renumbering or rewriting it as Social Graph.
5. Continue sequentially by the phase table and Master PRD dependencies.

## 5. How each phase is executed
For each phase, use this compact loop:
1. Read Master PRD, this file, `AGENTS.md`, and only the relevant code/docs.
2. Inspect all four repos (directories) and mark change/integrate/not affected before coding.
3. Implement the vertical slice in the same phase; update database migrations only when needed.
4. Run relevant automated tests/builds and fix failures.
5. Commit directly to `main`.
6. Update this table and report: commit, changed repos, tests actually run, blockers, and next phase.

Do not create a new phase document, checklist document, status CSV, or report file for routine work. Keep implementation notes in commits and update this plan only when the canonical status/next action changes.

## 6. Architecture invariants
- Master PRD v3.0.0 is the product authority; this file controls engineering execution only.
- Target surfaces: native Android/iOS, Web, separate Super Admin, and Developer Console. PWA is not a target.
- Supabase canonical project: `AllphaAiAplikasi-db` (`dvdziauyvuhcnqhrrvww`). Do not create a new database.
- API/domain business truth remains in `apps/api`; client apps must not bypass authorization.
- No production secrets in clients. No fake data presented as real integration.
- GLB/assets must use the canonical catalog/manifest; do not hard-code private Storage URLs.
- The four-repo checklist applies to every phase, not only ENG-P01.

## 7. What counts as done
A phase can be marked `implemented` only when its scoped code exists in all affected repos and relevant automated checks pass. Use `integration_verified` when real connected services are exercised, `acceptance_passed` when the phase acceptance journey has evidence, and `production_verified` only after production verification. If device tooling or credentials are unavailable, state the limitation and keep the phase in progress; do not substitute a document or CI-only pass.
