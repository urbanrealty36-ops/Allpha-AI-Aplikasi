# AGENTS.md — Allpha Universe Engineering Contract

## 0. Mandatory pre-execution gate: read the Master PRD first

**Every AI coding agent, autonomous agent, contributor, and implementation workflow MUST read and understand the complete current Master PRD before planning, generating, editing, deleting, migrating, deploying, or executing project changes. This is a hard gate, not a suggestion.**

Canonical product specification:
- `docs/PRD/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE.md`
- Document ID: `ALLPHA-MPRD-003`
- Version: `3.0.0`
- Treat this file as the primary product and engineering contract unless a formally approved ADR changes a specific decision.

Before making any change, an agent MUST:
1. Read the entire Master PRD, not only the section matching the immediate task.
2. Identify the affected product journey, domain(s) among the 82 capability domains, canonical engine owner, Phase and dependencies.
3. Read this `AGENTS.md`, the single fixed phase plan at `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md`, relevant architecture/API/schema/design-system documents, and existing code/tests/migrations.
4. Inspect the actual repository state, branch, latest commit, working tree/change context when available, existing patterns, and CI status. Never assume a file, feature, schema, endpoint, or runtime exists.
5. Reconcile the intended work against the Master PRD and existing implementation. Record contradictions, missing prerequisites, and unresolved decisions before implementation.
6. Produce a traceable execution plan mapping each applicable requirement to domain/module, API/event contract, data/schema/migration, UI states, authorization/privacy/security, observability, tests, acceptance criteria, and evidence.
7. If a real architecture decision remains unresolved, create/propose an ADR with options, trade-offs, consequences, migration/rollback implications, and owner. Mark dependent work blocked until approved; do not silently invent a decision.
8. Only then begin the approved implementation. For a small change, the plan may be concise but must still identify scope, safety implications, and validation.

If the Master PRD cannot be read, is missing, or conflicts with another instruction/source, **STOP before implementation**. Report the exact blocker and ask for the required document or decision. Do not substitute guesses, memory, an old repository, or generic assumptions for the Master PRD.

## 1. Authority and conflict resolution

- The Master PRD defines product behavior, domain ownership, security/privacy boundaries, lifecycle, acceptance, and delivery rules.
- This file defines the mandatory agent operating procedure.
- Approved ADRs may resolve explicitly open decisions or amend a narrow area of the PRD; cite the ADR and scope of the change.
- `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md` is the single operational engineering phase plan and must not silently override the Master PRD.
- If sources conflict, do not silently merge or overwrite them. Document the exact conflict, affected requirements, impact, and proposed resolution; block dependent implementation until resolved.
- Never treat a successful build, green CI, UI shell, table, endpoint, workflow graph, or mock-only test as proof that a feature is complete.

## 2. Product and architecture invariants

Agents MUST preserve these Master PRD constraints:

- Allpha is an **AI Social Universe for Humans and AI Agents**: social, Agent ecosystem, personal knowledge/learning, workflow automation, 3D living worlds, Live Experiences, marketplace, and creator economy.
- The target product surfaces are **native/mobile application, web application, separate Super Admin application, and Developer Console**. **PWA is explicitly not a target product or architecture component.** Do not reintroduce PWA scope without an explicitly approved architecture decision.
- This is a standalone new-build baseline. Do not assume legacy code, repositories, endpoints, deployments, database schemas, assets, or records are valid. Do not import an old project/repository implicitly.
- Primary product language: Bahasa Indonesia. Secondary: English.
- Keep one canonical engine as the authority for each domain lifecycle and business truth. Do not create duplicate registries, renderers, workflow engines, ledgers, or competing sources of truth.
- Use typed, versioned API/event contracts and validated schema boundaries. Clients must not perform privileged business writes directly.
- PostgreSQL is transactional source of truth; schema changes require version-controlled migrations, constraints, appropriate indexes, RLS where scoped, tests, and rollback/forward-repair planning.
- No fabricated business data in integration, staging, or production. Synthetic fixtures are allowed only in isolated tests and must be clearly test-only.
- Never embed provider/payment secrets, private credentials, or service-role keys in clients.
- AI Agent autonomy is bounded by owner intent, explicit permissions, policy, risk controls, approvals, and budget. Model output is not authority.
- Private memory/documents/credentials are not public by default. Filter retrieval at query time and enforce authorization outside the model.
- World/scene definitions must be declarative, schema-validated, and non-executable. Never execute AI-generated arbitrary code in a renderer or privileged backend.
- Long-running work must be bounded, observable, cancellable, idempotent where possible, and resumable from durable checkpoints.
- Theme/asset presence in storage or a catalog does not imply legal clearance, approval, publication, renderer compatibility, or production readiness.

## 3. Required operating sequence

Follow this sequence for every implementation task, adapting depth to task risk without skipping the Master PRD gate:

**READ → INSPECT → RECONCILE → PLAN → IMPLEMENT → MIGRATE (if needed) → TEST → SECURITY/PRIVACY CHECK → INTEGRATION/API VERIFICATION → UI/E2E VERIFICATION → EVIDENCE → REPORT**

1. **READ:** Master PRD, this file, phase plan, relevant ADRs and docs.
2. **INSPECT:** actual repo/branch/commit, existing implementation, tests, configuration, migrations, CI and configured dependencies.
3. **RECONCILE:** map requirements to current code and identify gaps, duplication, drift, blockers and decisions.
4. **PLAN:** create requirement-to-code-to-test traceability and a dependency-ordered vertical slice.
5. **IMPLEMENT:** deliver working UI, API, data lifecycle, permissions, failure/recovery behavior and observability for the owned Phase; do not create shells-only work.
6. **MIGRATE:** if data changes, add a versioned migration, test fresh install and upgrade path, and document safe rollback/forward repair.
7. **TEST:** run relevant unit, contract, integration, migration, authorization, regression, E2E and device tests.
8. **SECURITY/PRIVACY CHECK:** verify ownership, tenant isolation, permissions, RLS, secrets, SSRF/egress, rate/budget limits, audit, privacy and abuse cases as applicable.
9. **INTEGRATION/API VERIFICATION:** exercise real configured dependencies where required; explicitly label mock, sandbox, and real-integration results.
10. **UI/E2E VERIFICATION:** verify actual user journeys and loading/empty/success/error/disabled/retry/recovery states, accessibility, responsive behavior, and relevant native-device/browser matrix.
11. **EVIDENCE:** retain logs, test output, screenshots/video where applicable, migration results, traces, CI links, and known limitations.
12. **REPORT:** state changed files, commit/PR, requirement coverage, tests actually run, evidence links, status per completion contract, known issues, and next Phase/dependency.

## 3A. Mandatory implementation order for every feature/domain

This rule applies to every implementation involving Frontend, Backend, UI/UX, any of the 14 canonical 3D Theme GLB categories, features/domains, engines, business logic, orchestration, Workflow Engine, memory, Model Router/LLM, external APIs/providers, or architecture.

### Before implementation
1. Read the complete Master PRD, this AGENTS.md, and the fixed phase plan; then read the relevant ADRs, API/schema/design-system/asset contracts and current tests.
2. Inspect the actual `main` tree, current code, migrations/schema, CI, configuration and existing integration. Map the affected client(s) → typed FastAPI route/contract → service/canonical engine → repository/provider → canonical Supabase data, including ownership, permissions, failure paths and tests.
3. Record the owning ENG-P00–ENG-P37 phase, dependencies, acceptance criteria and coverage of Web, API/DB, Native Client, and Super Admin. Do not create a new phase or parallel checklist/status board. If source conflicts or a required decision is unresolved, document the exact blocker; do not guess.

### Default implementation order
Use this dependency order for a feature slice. “Develop” means inspect and change only what the scope requires; do not add needless schema changes or touch unaffected applications.

1. **Supabase database/schema:** inspect the existing canonical project first. If data changes are needed, add a version-controlled migration with constraints/indexes, least-privilege grants/RLS as applicable, and upgrade/repair strategy. Never create a second database or apply unsafe/destructive production changes without an approved recovery plan.
2. **Backend server — `apps/api`:** implement the typed/versioned FastAPI contract, trusted caller/resource context, authorization and policy/quota checks, application/domain service, canonical engine invocation, repository/provider access, stable errors and observability. The API owns business truth.
3. **Native Client — `apps/client` (Android/iOS):** implement the affected native journey against the canonical API contracts; keep behavior and business rules consistent with Web. Never bypass the API for business writes or call LLM/provider APIs directly.
4. **Web Client — `apps/web`:** implement the corresponding responsive web journey using the same canonical API contracts and business behavior as Native.
5. **Super Admin — `apps/super-admin`:** implement authorized operator/governance surfaces when the feature requires them; otherwise explicitly record `NOT AFFECTED` with a reason.
6. **End-to-end integration:** connect each affected client to the same `apps/api` domain contract, canonical service/engine, authorized data/provider path and Supabase source of truth. Reconcile environment configuration, authentication/session behavior, request/response schemas, loading/empty/success/error/retry/recovery states and observability. No mock or placeholder may be reported as a live integration.
7. **Functional verification and evidence:** run the smallest relevant checks during implementation and required contract, migration, authorization, integration, UI/E2E and device checks before claiming the applicable acceptance status. If the Product Owner defers full integration tests, mark them `DEFERRED / NOT VERIFIED`; do not claim all applications are fully integrated or phase acceptance has passed.

### Cross-cutting requirements
- UI/UX must follow the PRD and existing design system and implement real states/actions, accessibility and responsive behavior—not just a visual shell.
- 3D GLB work must use the 14 canonical keys in this file, inspect actual file metadata/integrity and map assets through the canonical API/catalog/manifest/renderer path. Storage presence or rendering alone does not prove publication rights or production readiness.
- AI/LLM execution must go through the canonical AI Gateway/Model Router. External API integrations must handle secrets server-side, timeouts, bounded retries, rate/budget limits, provider errors and idempotency where applicable.
- Keep all four application areas represented in the phase plan as `CHANGE`, `INTEGRATE`, or `NOT AFFECTED` with a reason. Update the owning fixed-phase row in the same direct-to-`main` commit when status or next action changes.
- Never claim a test, migration, integration, visual/device QA or deployment passed unless its actual result was observed. Keep phase status evidence-based.

## 4. Phase and completion rules

- Every Phase must be a usable vertical slice including UI, API, data, domain engine, permissions, failure states, observability, documentation, integration, and acceptance tests.
- Do not defer missing business logic, authorization, integration, or UI behavior to the final QA Phase.
- Use the Master PRD completion statuses exactly and do not collapse them into a single “done” label:
  - `not_started`
  - `in_progress`
  - `blocked`
  - `implemented`
  - `integration_verified`
  - `acceptance_passed`
  - `production_verified`
- Advance a Phase only after its acceptance journey passes and required evidence is retained. A green CI run alone is insufficient.
- Report the next Phase only after current Phase status is supported by evidence. If blocked, name the blocker and the specific action/decision needed to unblock it.
- The engineering execution sequence is ENG-P00–ENG-P37 as defined in `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md`; the Master PRD remains product authority. Do not invent additional Phase numbering.

## 5. Domain ownership, APIs, data and migrations

For each affected domain, identify its canonical owner and lifecycle before changing code. Modules should define API schemas/routes, application logic, repository/data access, authorization, events, idempotency/transaction behavior, workers, error taxonomy, observability, migrations, tests, and user/admin UI dependencies as applicable.

For each request:
- Authenticate the caller where required and derive owner/tenant/resource context from trusted server state.
- Validate payload/schema and size; enforce permission, rate/concurrency limits, budget/quota and policy before effects.
- Do not trust client-supplied `owner_id`, `tenant_id`, `role`, `price`, `credit_balance`, `payment_status`, or `published=true` as authority.
- Use stable error contracts and request/trace IDs.
- Keep storage binaries separate from database metadata and expose only authorized references/manifests.
- Make migrations repeatable and test against a fresh database plus upgrade path. Do not apply destructive production changes without an approved plan and recovery path.
- Do not assume a configured Supabase project contains schema, migrations, or seed data; inspect its real state first and reconcile before changes.

## 6. AI, memory, workflows and costs

- All model/provider execution must route through the canonical AI Gateway and Model Router; no feature-specific provider bypass.
- Register provider/model capability, policy, budget, limits, usage and fallback behavior explicitly. Do not hard-code a provider choice that the PRD leaves open; resolve through approved configuration/ADR.
- Count self-hosted inference costs (GPU, power/cloud, storage, bandwidth, monitoring, security, operations); do not describe it as free.
- Bound tokens/context, loops, tool calls, retries, concurrency, runtime and spend. Reserve, meter, settle and release budget accurately.
- Tools require strict schemas and external authorization; high-risk actions require approval; side effects need idempotency where possible.
- Distinguish working, episodic, semantic, procedural, long-term, corpus and published knowledge. Memory writes require policy/consent/provenance and deletion propagation.
- Workflows must be versioned, validated, durable, checkpointed, resumable and observable. Do not duplicate the canonical Workflow Engine inside Orchestration.

## 7. Spatial/3D asset and renderer rules

- Follow the PRD spatial hierarchy: `Universe/Galaxy → World → District → Zone → Booth/POI → Scene Object / Media Surface`.
- Use versioned declarative World/Scene Schema, authorized manifests and a canonical Theme/asset lifecycle.
- Asset lifecycle: `draft → uploaded/quarantined → validating → review → approved → published → deprecated/retired`, with documented rejection/failure/block/revocation paths.
- Public manifests may expose only approved, published, authorized versions.
- Before promotion, verify source/provenance, exact license and derivative rights, file integrity, security, moderation, schema compatibility, rig/animation capability where relevant, performance budgets and renderer compatibility.
- Structural parsing or a successful download is not visual QA or production approval. Report each evidence category separately.
- Use lazy/chunked loading, LOD/texture variants, culling/instancing as supported, device profiles, safe cancellation/retry, and non-3D/low-detail fallback.
- Do not claim character lip-sync, skeletal motion, or facial animation unless the asset's actual rig/blendshape/viseme capability supports it.

## 8. Security, privacy, payments and governance

- Apply least privilege, RBAC plus resource/attribute/context checks, tenant isolation, RLS defense-in-depth, secret vault/rotation/redaction, safe upload quarantine, sandboxed parsers, SSRF/egress defenses, rate limits, quotas, audit and incident controls.
- Test direct and indirect prompt injection, cross-user/tenant data leakage, IDOR, unauthorized tools, credential revocation, unsafe media/document access, malicious assets, and fraud where relevant.
- Payment settlement must be verified server-side and idempotent. A client redirect is never proof of payment. Refunds/reversals must preserve ledger history.
- Credits and rewards are governed ledgers; AI Credits are not automatically cash.
- Ads, content, Agents, themes and assets require eligibility, moderation, rights, budget and takedown controls.
- Super Admin privileges require dedicated authorization, confirmation for risky operations and audit; hidden UI is not a security control.

## 9. Open decisions and ADRs

The PRD intentionally leaves decisions open, including mobile cross-platform stack/3D/WebRTC spike, web framework, queue/workflow worker technology, media SFU/TURN, voice runtime, embedding/reranking providers, self-hosted inference capacity, 3D generation adapters/licensing, storage/CDN, plan quotas/prices, creator reward/cash-out policy, retention/deletion SLAs, device performance targets, SLO/RPO/RTO, and final 14-category asset taxonomy.

Do not silently settle these. Create an ADR before production implementation of the affected decision, with context, options, trade-offs, decision, consequences, owner and migration/rollback implications.

## 10. Evidence-based reporting template

Every implementation report MUST include:
- **Phase / task:** canonical phase and scope.
- **PRD traceability:** relevant section(s), domains, requirements and acceptance journey.
- **Repository baseline:** branch, commit before/after, files changed, PR/commit URL.
- **Status:** one of the explicit completion statuses above, with reason.
- **Tests:** exact commands/scenarios and pass/fail/skipped result; identify mock/sandbox/real dependency.
- **Security/privacy:** checks performed and outstanding risks.
- **Integration/deployment:** environment and evidence, without exposing secrets.
- **Evidence bundle:** CI/test/log/visual/device links or artifact references.
- **Known gaps/blockers:** no hidden or silently deferred work.
- **Next step:** next dependency-ordered task or Phase and its entry criteria.

Never claim a command, test, migration, deployment, visual inspection, real-device test, integration, upload, or release occurred unless its result was actually observed.


## Mandatory Phase Plan Study, Reconciliation, and Evidence-Gated Check-off

Before any planning, code generation, editing, migration, deployment, or execution, every human/AI agent MUST:
1. Read the entire canonical Master PRD at `docs/PRD/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE.md`.
2. Read the single operational phase plan at `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md` and only the relevant technical/architecture documents that remain actively referenced by it. Do not require legacy phase plans, per-phase documents, crosswalks, or separate status boards.
3. Inspect the repository default branch/head, source tree, tests, migrations, CI, artifact manifests, and current evidence; inspect live backend/database state only through authorized canonical connectors and official APIs.
4. Reconcile requirements, phase dependencies, domain/API/data ownership, UI/UX, security/privacy, tests, and acceptance criteria before proposing implementation. If source docs conflict or required evidence is missing, record the conflict/blocker and stop rather than silently guessing.
5. Do not mark a phase/checklist item complete because code was written, an asset downloaded, a file exists in Storage, a screenshot looks correct, or CI is green. Tick `[x]` and set `COMPLETE` only when that individual acceptance criterion has reproducible linked evidence covering its required backend/data/API, UI, security/privacy, integration/E2E, runtime/device and operational checks.
6. After each implementation change, update the affected row/next action in `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md` in the same direct-to-main commit when phase status or next action changes. Record the commit, relevant checks, actual integration evidence, limitations, and next dependency. Do not create a separate status board or routine evidence report. Keep status evidence-based and never mark dependent phases complete automatically.
7. For GLB publication, preserve the complete lifecycle: inventory/provenance and available rights information → automatic basic GLB readability/format/integrity checks → manifest/catalog mapping through the canonical API → developer preview and renderer integration → audience publication only where rights and applicable policy permit. Do not create redundant manual approval stages for ordinary developer preview. Never bypass the canonical backend or claim public rights/production approval from file presence alone.
8. The 14 canonical 3D category keys are `universe`, `galaxy`, `world`, `orbit`, `capsule`, `district`, `booth`, `content-feed`, `agent-character`, `live-stage`, `human-live`, `sticker-social`, `animation`, and `navigation-fx`. A category mapping is a candidate until supported by actual file metadata/geometry and evidence. Never fabricate a per-file inventory or force-fit a category.
9. The 25 Themes × 14 categories are 350 template slots, not proof of 350 unique approved assets. District city scenes use validated Scene Schema/World DSL and canonical backend entity IDs; GLBs provide presentation only and cannot grant permission, ownership, billing, entitlement or moderation state.
10. Final Phase 37 is a validation/release gate, not a place to hide missing feature implementation. Return any missing capability to its owning phase and preserve traceability.



## 11. Product Owner execution mode — direct main and lightweight delivery (2026-10-13)

The Product Owner has explicitly directed that implementation work be committed directly to `main`. Do not create new working branches or require a pull request for routine changes. Use direct commits on `main` through the connected GitHub integration. Do not create approval gates, manual sign-offs, multi-stage asset publication workflows, or excessive CI checks that delay normal product implementation. Keep the default CI to a small build/test smoke check and fix failures directly on `main`.

Build Allpha in the existing canonical GitHub monorepo `urbanrealty36-ops/Allpha-AI-Aplikasi`. Its architecture has exactly **three client/frontend applications and one backend application area**—not four frontend applications and not four separate Git repositories:
- `apps/web`: Web client (Next.js).
- `apps/client`: Native end-user client for Android/iOS (React Native + Expo; not a PWA).
- `apps/super-admin`: separate Super Admin client.
- `apps/api`: the one canonical backend, Python + FastAPI, owning API contracts, domain/application services, authorization, data access, migrations and engine invocation.
These are four logical application areas inside one monorepo. Do not invent, add, rename, or duplicate `apps/backend` while `apps/api` is canonical. Do not describe the backend as a fourth client. All three clients call the same canonical backend domain contracts; expose clear configuration/API boundaries so each can be extracted into its own repository later only if explicitly directed.

GLB developer workflow: assets available to the owner/developer should be able to flow from Storage/catalog to the UI renderer through a straightforward catalog/manifest/API path, without a mandatory manual approval chain. Keep only automatic basic file readability/format checks and a clear failure state. Do not claim legal rights, public authorization, or production readiness merely because an asset renders; where asset rights or user safety are uncertain, make that limitation visible without blocking local developer preview. Do not create a parallel asset registry or bypass the canonical backend for privileged writes.

The owner has asked to defer elaborate security/validation governance in favor of building working applications and integrations. Implement pragmatic, lightweight controls as part of each feature; do not turn optional audits or future hardening into blockers for ordinary development. Never expose secrets in clients, never fabricate live business data, and never claim unperformed tests/integrations succeeded. These basic correctness requirements are not a workflow approval gate.

Preferred execution loop: read relevant source/docs → implement directly on main → run the smallest relevant smoke test → report commit, what works, known gaps, and next phase. Do not stop implementation just because a later phase will add deeper hardening.


## 12. Mandatory topology and client-to-engine boundary (read before every implementation)

### 12.1 Canonical application count and ownership

The canonical repository is one GitHub monorepo: `urbanrealty36-ops/Allpha-AI-Aplikasi`. Inside it there are exactly three client applications and one backend application area:
1. **Web client:** `apps/web`.
2. **Native client (Android/iOS):** `apps/client`.
3. **Super Admin client:** `apps/super-admin`.
4. **Canonical backend only:** `apps/api` — Python/FastAPI.

The phrase “four application areas” means these three clients plus one backend; it never means four frontend clients. The API/backend is not a UI client. `apps/api` is canonical: do not create or assume a second `apps/backend`, a parallel API server, or a duplicate engine. Keep the current monorepo; do not split or create repositories unless the Product Owner explicitly directs it.

### 12.2 Required request path

For every business feature, the default and required path is:

`Web / Native / Super Admin → typed/versioned FastAPI endpoint → authentication + trusted caller/tenant/resource context → authorization/policy/quota → application/domain service → canonical domain engine (when owned/required) → repository/data provider → response/event`.

The backend is the authority for business truth, permission decisions, domain lifecycle, billing/credits, publication status, workflow state, Agent actions, memory policy, model selection and usage metering. The client may render state and perform presentation-only validation; it must not reimplement or bypass authoritative business logic.

### 12.3 Database and provider access rules

- Client-side Supabase Auth for sign-in/session lifecycle is permitted where the existing auth contract requires it. This exception does **not** authorize direct client reads/writes to business tables or privileged RPCs.
- Clients MUST NOT use Supabase/Postgres table queries, RPC, or direct provider SDK calls to bypass FastAPI for business/domain operations. This includes client-side business writes and privileged operations, even if a publishable key or RLS is present.
- Supabase Storage, Realtime, or other direct client data-plane access is permitted only where an explicit existing PRD/API contract authorizes it, scope is limited to the signed-in user/resource, and security rules/RLS are verified. Otherwise use backend-issued authorized references, URLs, subscriptions or API operations. Never hardcode private URLs or embed service-role/provider secrets in a client.
- AI/LLM/model-provider calls for Allpha features MUST pass through the canonical backend AI Gateway and Model Router. No client-side provider key, direct LLM SDK call, feature-specific provider bypass, or model policy/budget decision in the UI.
- Workflow execution, orchestration, memory writes/retrieval, agent tools, credits, commerce/settlement, asset catalog/lifecycle, moderation and Super Admin actions must use their canonical backend-owned services/engines. UI visibility is not authorization.
- RLS is defense-in-depth; it does not replace backend business rules, tenant authorization, policy checks, quotas, audit or engine invocation.

### 12.4 Mandatory source-to-engine mapping before coding

Before modifying a feature, the agent MUST inspect actual files and produce a concise traceability map with:
- client surface(s) and exact source files;
- API client/configuration and exact FastAPI route + request/response schema;
- application/domain service invoked by that route;
- canonical engine owner and exact call path (or explicit evidence that no engine applies);
- repository/query/provider path and relevant schema/migration;
- authentication, ownership, tenant, permission, budget/quota and audit behavior;
- tests covering allowed and denied paths, including proof that clients cannot bypass the API.

Do not guess module paths or infer that an engine exists because its name appears in documentation. If an engine/service/endpoint is absent or disconnected, report it as a gap and implement it in the canonical backend within the owning Phase; do not create a shadow implementation in a client.

### 12.5 Mandatory direct-database audit

For each of the three clients, search and review all database/provider access patterns, including `createClient`, `.from(`, `.rpc(`, generated DB clients, REST calls to Supabase, and Storage/Realtime subscriptions. Classify every result as:
- allowed authentication/session operation;
- explicitly authorized Storage/Realtime/data-plane exception with contract and scope;
- prohibited business-table/RPC/provider bypass;
- unused/dead code requiring removal or explanation.

Fix every confirmed bypass in the owning Phase, add a regression check where practical, and record the evidence in the fixed phase plan. Do not claim the audit passes based on search alone; trace call sites and run relevant tests.

### 12.6 Required pre-implementation gate

Before any code change, the agent MUST read the complete Master PRD, this AGENTS.md, and the fixed phase plan; inspect the current `main` tree and CI; identify the owning Phase and canonical engine; and complete the source-to-engine map above. If repo structure or source documents conflict, stop and report the exact contradiction instead of silently inventing another application or backend. No Phase can be marked `integration_verified`, `acceptance_passed`, or `production_verified` until the real client → API → service/engine → authorized data path and negative/bypass tests have evidence.

## 13. Product Owner testing sequence — implement phases first, full staging audit at ENG-P37

The Product Owner has explicitly directed that **full real-environment integration testing, staging-based acceptance, and consolidated end-to-end/security audit are deferred until the final validation phase, ENG-P37**, after all feature phases ENG-P00–ENG-P36 have been implemented. This instruction changes the timing of the consolidated staging test campaign; it does not authorize fabricated results, unsafe production testing, or skipping implementation-time checks.

### 13.1 During each implementation phase (ENG-P00–ENG-P36)

Follow the implementation order for the affected vertical slice:

1. Read the relevant requirements in the complete Master PRD, this file, and the single fixed phase plan; inspect existing source, schema/migrations, contracts, and dependencies.
2. **Supabase database/schema:** inspect the canonical schema and existing data path first. If the feature requires a schema change, implement a versioned migration and relevant constraints/indexes/grants/RLS. Do not create another project/database or use canonical production as a test database.
3. **Backend server (apps/api):** implement the typed/versioned FastAPI contract, validation, trusted identity/resource context, authorization/policy, domain service/engine, data access, errors and observability.
4. **Native Client (apps/client):** implement the corresponding Android/iOS user journey through the canonical API.
5. **Web client (apps/web):** implement the matching responsive journey using the same API contracts and business behavior as Native.
6. **Super Admin (apps/super-admin):** implement authorized operator surfaces where the feature requires them; otherwise record NOT AFFECTED and the reason.
7. **Integrate the path:** connect client → FastAPI endpoint → service/engine → repository/provider → canonical Supabase data path. Keep one backend/API as the business source of truth.
8. Run **lightweight implementation-time checks** appropriate to the change, such as unit/source regression tests, typecheck, lint, build, contract/schema checks, migration static checks, and CI smoke tests. Fix failures that can be safely verified in the current environment.
9. Record actual checks and results in the owning row of the fixed phase plan when status/next action changes. State explicitly which checks are automated/source-only and which real integrations have not been exercised.

### 13.2 Deferred until ENG-P37 — consolidated staging and real acceptance

After all implementation phases ENG-P00–ENG-P36 have working implementation slices, use ENG-P37 for the consolidated real-environment campaign, including as applicable:

- Verify an **already-existing, explicitly confirmed non-production/staging environment** and its database target before running live tests. Never assume an environment is staging because of its name.
- Run real Supabase authentication, data-path, migration fresh-install/upgrade, RLS/grants, owner/tenant isolation, and cross-user negative tests.
- Run authenticated client journeys across Web, Android and iOS where toolchains/devices are available, and the separate Super Admin application.
- Verify the complete client → API → canonical service/engine → Supabase path, external integrations, deployment health, failure/retry/recovery, security/privacy and relevant observability.
- Retain CI links, command/test results, logs, migration outcomes, deployment evidence, and browser/device screenshots or recordings where available.
- Return any discovered missing feature or domain behavior to its owning ENG-P00–ENG-P36 phase; ENG-P37 must not become a substitute implementation phase.

Do not create a new Supabase project or branch merely to satisfy this sequence. If no existing isolated staging environment is available at ENG-P37, report the exact blocker and request an approved environment; do not run destructive, tenant-isolation, or migration experiments against canonical production.

### 13.3 Status and truthfulness rules during the deferral

- Deferring the consolidated staging campaign is **not** the same as passing it. Until real dependencies have been exercised, describe that evidence as DEFERRED / NOT VERIFIED.
- During implementation phases, use source-level and automated checks to find/fix defects early; do not defer obvious correctness, authorization, privacy, secret-handling, or API-boundary defects until ENG-P37.
- Do not claim integration_verified, acceptance_passed, or production_verified for a real integration merely because source code, mock tests, a green build, or CI smoke tests exist.
- Keep the phase status evidence-based and update the fixed phase plan. The next phase may proceed according to the dependency order while deferred staging evidence remains explicitly open for ENG-P37, provided the implementation is present and no known safety-critical defect blocks the work.

