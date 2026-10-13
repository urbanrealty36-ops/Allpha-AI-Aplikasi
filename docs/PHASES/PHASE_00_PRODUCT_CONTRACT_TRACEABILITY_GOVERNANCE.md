# Phase 00 — Product Contract, Requirement Traceability & Delivery Governance

- **Canonical phase:** 00
- **Status:** `in_progress` — governance package authored; acceptance review and evidence-backed check-off remain open.
- **Authority:** Master PRD `ALLPHA-MPRD-003 v3.0.0`; `AGENTS.md`; Phase Master Plan v1.1.0.
- **Scope boundary:** product/engineering contract and delivery governance only. This phase does not claim that the application, native clients, backend runtime, renderer, or business features have been implemented.

## 1. Purpose and outcomes

Create one traceable contract for product, design, mobile, web, backend, spatial/3D, security, QA and operations so contributors build the same product and can demonstrate what is implemented.

Outcomes:
1. Stable product invariants and terminology.
2. Unique requirement IDs and traceability to domain, phase, acceptance criteria and evidence.
3. Canonical domain/engine ownership and dependency ordering.
4. ADR register for unresolved decisions; no silent architecture choices.
5. Data classification, lifecycle, API/event/error contract rules.
6. Branch/PR/review, migration, test, evidence and release policies.
7. Explicit status board that distinguishes documentation from implemented product capability.

## 2. Source authority and conflict rules

| Priority | Source | Authority |
|---|---|---|
| 1 | `docs/PRD/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE.md` | Product behavior, domain ownership, security/privacy, lifecycle, acceptance and NFRs |
| 2 | `AGENTS.md` | Mandatory agent operating procedure and evidence rules |
| 3 | `docs/PHASES/ALLPHA_UNIVERSE_IMPLEMENTATION_PHASE_MASTER_PLAN_v1.1.0.md` | Delivery sequence and phase scope |
| 4 | Approved ADRs | Resolve a named open decision or explicitly amend a narrow PRD area |
| 5 | Phase-specific implementation docs | Operational detail subordinate to the above |

If two sources conflict, record the exact passages, impact, proposed options and affected phases in the ADR/risk register. Mark dependent work `blocked` until an authorized decision is recorded. Do not silently merge sources.

## 3. Canonical product contract

- Allpha is an **AI Social Universe for Humans & AI Agents**, combining human identity, owned AI Agents, knowledge and memory, workflows, social content, collaboration, spatial worlds, live experiences, marketplace and creator economy.
- Build from a clean baseline. Existing GLB acquisition/audit scripts are preparatory tooling only; they are not proof that the product application exists.
- Target surfaces: native/mobile application, web application, separate Super Admin application and Developer Console. PWA is not a target product.
- Primary language: Bahasa Indonesia. Secondary language: English. Design mobile-first while retaining appropriate web affordances.
- Business truth and state changes must flow through canonical backend APIs and the transactional database. Client-side state is not authority.
- Use one canonical engine/registry/lifecycle per domain. No competing source of truth or permanent production stubs.
- Human owns the Agent. Agent actions are bounded by owner intent, explicit permissions, platform policy, approval and budget.
- Private data is default-deny. Enforce authorization at the server/query boundary; model prompts and UI visibility are not security controls.
- No fabricated business data in integration, staging or production. Synthetic fixtures are permitted only in clearly isolated tests.
- Secrets and privileged credentials remain server-side.
- Asset presence/download/structural validity is not proof of licensing, moderation approval, publication, renderer compatibility or production readiness.
- Every phase is evidence-gated; code written, build green or UI visible alone does not mean complete.

## 4. Scope and non-goals

### In scope
- Requirement decomposition and traceability.
- Domain/engine ownership map and phase dependency map.
- Glossary and entity naming conventions.
- Data classification and lifecycle vocabulary.
- API/event/error/versioning principles.
- ADR and risk registers.
- Branch/PR/review, migration, test, evidence and release policies.
- Reusable phase, test, evidence and release report templates.

### Explicitly out of scope
- Implementing mobile/web screens or backend business features.
- Selecting unresolved mobile/web frameworks, queue, SFU/TURN, voice provider, inference provider or final asset taxonomy without an ADR.
- Publishing GLBs or writing asset registry records.
- Marking Phase 01–37 complete.
- Treating a documentation commit as proof of a deployable product.

## 5. Requirement ID convention

Requirement IDs are stable and must not be recycled:
- `ALLPHA-PRD-001`: document-level product/engineering contract.
- `ALLPHA-PROD-###`: product and user journeys.
- `ALLPHA-DOM-###`: domain/engine ownership.
- `ALLPHA-SEC-###`: security, privacy, trust and governance.
- `ALLPHA-DATA-###`: data model, ownership, lifecycle and migration.
- `ALLPHA-API-###`: API/event/error/versioning contracts.
- `ALLPHA-SPATIAL-###`: spatial/3D asset and runtime contract.
- `ALLPHA-OPS-###`: CI/CD, reliability, observability and release.
- `ALLPHA-NFR-###`: performance, accessibility, localization and resilience.
- `ALLPHA-PHASE-##-###`: phase-specific acceptance criteria.

IDs reference PRD sections and domains in the Requirement Traceability Matrix. If the PRD changes, preserve the old ID and record supersession rather than silently renumbering.

## 6. Domain and engine ownership rules

1. Every business entity has one canonical lifecycle owner.
2. Other domains use versioned APIs/events/contracts; they do not directly mutate another domain's private tables or duplicate its lifecycle.
3. Authorization is evaluated for actor + action + resource + context; roles alone are insufficient for resource access.
4. The backend is authoritative for ownership, visibility, entitlement, payment, credits, publication, moderation and Agent permissions.
5. Event consumers must handle duplicate/out-of-order delivery safely where applicable.
6. Scene/World schemas are declarative and validated; scene data cannot grant permission or execute arbitrary code.
7. Asset manifests expose only approved, published and authorized versions.
8. Cross-domain dependency must be explicit in the Phase Plan and tests.

The canonical 82-domain inventory and proposed phase ownership are maintained in [Requirement Traceability Matrix](./REQUIREMENT_TRACEABILITY_MATRIX.md).

## 7. Naming, status and lifecycle vocabulary

### Phase statuses
Use only the Master PRD completion statuses: `not_started`, `in_progress`, `blocked`, `implemented`, `integration_verified`, `acceptance_passed`, `production_verified`.

### Evidence/checklist statuses
Use `NOT_VERIFIED`, `IN_PROGRESS`, `BLOCKED`, `IN_REVIEW`, `VERIFIED`. `VERIFIED` requires a reproducible evidence reference and reviewer. A checklist item cannot be checked based on assumption.

### Asset lifecycle
`draft → uploaded/quarantined → validating → review → approved → published → deprecated/retired`, with explicit failure, rejection, block and revocation paths. Downloaded or structurally valid assets are not automatically approved.

### API and event contracts
- Version externally consumed contracts; document compatibility and deprecation.
- Validate all boundary inputs; use stable error codes and a request/correlation ID.
- Keep server error details safe; never leak secrets or private content.
- Use idempotency keys for financial, publication and other side-effecting operations where appropriate.
- Document authentication, authorization, rate/budget limits, pagination, retries, timeout and cancellation behavior.

## 8. Data classification

| Class | Meaning | Default handling |
|---|---|---|
| `public` | Explicitly approved for public access | Publish only through authorized APIs and lifecycle |
| `internal` | Operational/product information not intended for public users | Authenticated access by least privilege |
| `private` | User/Agent/tenant-owned data | Owner/resource-scoped authorization; default deny |
| `sensitive` | Personal, financial, identity, private knowledge or other high-impact data | Minimize, narrowly authorize, audit where appropriate, define retention |
| `secret` | Tokens, passwords, signing keys, provider/payment credentials | Secret manager only; redact from logs; rotate/revoke |
| `system-only` | Internal policy, security controls, privileged diagnostics | Explicit privileged access and audit; never expose by default |

Data owners must define purpose, audience, retention, deletion propagation, export rights, logging rules and any provider-processing disclosure before production use.

## 9. Architecture Decision Records (ADR)

ADRs are stored in `docs/architecture/adr/` using `ADR-NNNN-short-title.md`. Required sections: status, context, requirements, options, trade-offs, decision, consequences, security/privacy, migration/rollback, owner, approver and evidence.

No ADR is considered approved merely because it is drafted. Open decisions and phase impact are tracked in [ADR and Risk Register](./ADR_AND_RISK_REGISTER.md). An unresolved decision blocks only the implementation that depends on it, not unrelated work.

## 10. Delivery governance

### Branch and PR
- Work on a scoped branch and submit a PR to `main`; do not use direct-to-main changes for normal feature work.
- PR must state phase, scope, requirements, design/API/data/security impact, migration, tests, evidence, risks and rollback.
- Require review by a maintainer; high-risk security, payment, privacy or destructive migration changes require an appropriate domain/security review.
- Keep commits scoped and messages imperative; do not include secrets, generated binaries or unrelated changes.
- Never rewrite shared history or force-push protected/default branches without explicit authorization.

### CI quality gates
- Format/lint/type/static checks for the languages actually present.
- Unit and contract tests for changed behavior.
- Dependency/security scanning and secret scanning.
- Migration validation and schema drift checks when database artifacts change.
- Build artifact provenance and commit association.
- Integration/E2E gates must use explicitly configured dependencies; mocks must be labelled and cannot count as production evidence.

### Database and migration
- Inspect the real target project before proposing schema changes.
- Store migrations in version control; make them deterministic, ordered and safe to retry.
- Test fresh install and upgrade path; document rollback or forward-repair strategy.
- No destructive production migration without reviewed recovery plan and backup/restore evidence.
- Do not fabricate schemas or assert Supabase readiness without inspection.

### Testing policy
- Test success, empty, invalid input, unauthenticated, forbidden, not found, conflict, timeout, retry, cancellation and recovery where relevant.
- Verify owner/tenant isolation and negative authorization paths.
- Use synthetic fixtures only in isolated test scope; never use fixtures to claim real integration.
- Record exact commands, environment class, result, skipped tests and known limitations.

### Evidence registry
Every phase evidence bundle must be linked from `docs/evidence/PHASE-XX/` or an explicitly documented external CI/artifact URL. Do not commit secrets, raw private user data or oversized binaries as evidence. Include:
- requirement/acceptance ID;
- commit/PR and build;
- test command/scenario and output;
- migration/API/authorization evidence where relevant;
- UI screenshot/video and device/browser matrix where relevant;
- integration target classification (mock, sandbox, staging, production);
- reviewer, date, known limitations and decision.

### Release train
A release candidate must map to an immutable commit and environment. Release notes identify features, migrations, known issues, security review, rollback plan and evidence. Production verification is distinct from implementation and acceptance testing.

## 11. Severity and blocker policy

| Severity | Definition | Handling |
|---|---|---|
| `S0 Critical` | Active compromise, data exposure, payment/security boundary bypass, unrecoverable corruption | Stop release/affected work; incident response immediately |
| `S1 High` | Major journey unusable, cross-owner leak, authorization failure, critical data loss or financial integrity risk | Block phase/release until fixed or explicitly risk-accepted by authorized owner |
| `S2 Medium` | Material feature degradation with workaround; bounded operational risk | Fix before phase acceptance unless documented exception approved |
| `S3 Low` | Cosmetic/minor issue with negligible risk | Track with owner and target milestone |

A blocker record must include ID, observed evidence, impact, affected requirements/phases, mitigation, owner, and exact exit condition. Security/privacy/financial-integrity failures cannot be waived by a UI-only workaround.

## 12. Requirement change control

1. Submit change request with reason, source, affected requirement IDs, domains, phases, data/API/UI/security impacts, migration and backward-compatibility effects.
2. Identify conflict with existing PRD/ADR and affected acceptance tests.
3. Record decision and approver. Update PRD only through a reviewed, versioned change.
4. Update traceability matrix, phase plan, ADR/risk register and tests in the same PR where practical.
5. Retain superseded decisions and requirement links; do not erase history.

## 13. Phase completion gate

A phase is not complete until its acceptance criteria and dependencies are evidenced. For the Phase 00 documentation/governance deliverables, the gate requires:
- [ ] PRD and Phase Plan requirements are mapped to stable IDs.
- [ ] 82-domain ownership and proposed phase mapping reviewed.
- [ ] Dependencies and open architecture decisions are recorded.
- [ ] Glossary, status, data-classification and lifecycle vocabulary approved.
- [ ] Branch/PR, CI, migration, test, evidence and release policies reviewed.
- [ ] Risks have owners or explicit owner-assignment blockers.
- [ ] Contradictions between Master PRD roadmap (00–24) and Phase Plan v1.1.0 (00–37) are recorded and approved as a source-of-truth decision.
- [ ] Repository structure/CI/test baseline inspected and attached as evidence.
- [ ] Phase 00 artifacts reviewed and acceptance sign-off recorded.

## 14. Known source reconciliation issue

The Master PRD Part XVIII describes a Phase 00–24 roadmap with phase names that do not align one-to-one with the 00–37 Phase Master Plan. `AGENTS.md` also states the PRD roadmap currently defines 00–24 and prohibits claiming later numbering as canonical without reconciliation. Phase Plan v1.1.0 declares itself the current implementation plan and defines 00–37. This is a material governance conflict. It is recorded as `ADR-0001` and must be explicitly approved before treating the 00–37 mapping as an amendment to the PRD roadmap. Until resolved, the Phase 00 package can be authored, but the overall phase numbering authority remains a blocker for dependent phase check-off.

## 15. Deliverables
- `docs/PHASES/PHASE_00_PRODUCT_CONTRACT_TRACEABILITY_GOVERNANCE.md` — this contract.
- `docs/PHASES/REQUIREMENT_TRACEABILITY_MATRIX.md` — requirements, 82 domains, proposed phase mapping and evidence slots.
- `docs/PHASES/ADR_AND_RISK_REGISTER.md` — open decisions and delivery risks.
- `docs/PHASES/MASTER_PRD_SECTION_TRACEABILITY.md` — section-level routing for all 91 numbered PRD sections.
- `docs/PHASES/PHASE_EXECUTION_TEMPLATES.md` — reusable phase, test, evidence, release and change-request templates.
- Update to Phase Master Plan status/links after read-back verification.
- Phase 00 evidence report after acceptance review; no evidence is fabricated in advance.


## ADR-0001 review status (2026-10-13)

The Product Owner has explicitly approved Option 3: separate the Master PRD product-roadmap namespace (`PRD-P00`–`PRD-P24`) from the detailed engineering execution namespace (`ENG-P00`–`ENG-P37`) and maintain an explicit crosswalk. Engineering Lead approval is still pending; ADR-0001 must not be marked accepted yet.

- Crosswalk: [Phase Roadmap Crosswalk](./PHASE_ROADMAP_CROSSWALK.md).
- Decision register: [ADR and Risk Register](./ADR_AND_RISK_REGISTER.md).
- Phase Master Plan and section traceability have been annotated with the interim approval state.
- Master PRD and `AGENTS.md` are intentionally unchanged until required Engineering Lead review and any separately approved source changes.
- Phase 00 remains `in_progress`; no Phase 01 start/acceptance claim is made by this update.
