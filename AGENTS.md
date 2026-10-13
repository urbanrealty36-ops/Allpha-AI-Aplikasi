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
3. Read this `AGENTS.md`, the current Phase/implementation plan, relevant architecture/API/schema/design-system documents, and existing code/tests/migrations.
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
- Phase plans sequence work but must not silently override the PRD.
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
- The PRD roadmap currently defines Phase 00 through Phase 24. Do not invent additional Phase numbering or claim later roadmap items are canonical without reconciling an approved plan/ADR.

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
