# Allpha Requirement Traceability Matrix (RTM)

- **Baseline PRD:** `docs/PRD/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE.md` (ALLPHA-MPRD-003 v3.0.0)
- **Phase sequence under reconciliation:** `docs/PHASES/ALLPHA_UNIVERSE_IMPLEMENTATION_PHASE_MASTER_PLAN_v1.1.0.md`
- **Status:** Baseline mapping draft for review. A proposed phase mapping is not implementation evidence.
- **Rule:** Requirement IDs are stable. Update this matrix with implementation commit, test and evidence links as each requirement is implemented. Never mark `VERIFIED` without reproducible evidence.

## 1. Cross-cutting requirements

| ID | Requirement | PRD reference | Owner | Proposed phase(s) | Acceptance / evidence required | Status |
|---|---|---|---|---|---|---|
| ALLPHA-PRD-001 | Master PRD is the product and engineering authority | Part I §§1–4 | Product governance | 00 | Reviewed product contract; conflicts logged | IN_REVIEW |
| ALLPHA-OPS-001 | Requirement-to-code-to-test traceability | Part XVIII §82; Part XIX §§83–85 | Delivery governance | 00, 37 | Every requirement maps to owner, dependency, acceptance and evidence | IN_PROGRESS |
| ALLPHA-OPS-002 | Phase and release status must be evidence-based | Part XIX §§83–84 | QA/release | 00, 36, 37 | Reproducible CI/test/API/UI/security evidence | IN_PROGRESS |
| ALLPHA-OPS-003 | Clean new-build baseline; no legacy dependency assumption | Part I; AGENTS.md | Platform architecture | 00, 01 | Repository/dependency inspection and approved architecture | IN_PROGRESS |
| ALLPHA-OPS-004 | Native/mobile, web, Super Admin and Developer Console are product surfaces; PWA excluded | Part II §7; AGENTS.md | Product/platform | 00, 01 | Approved surface architecture and builds | IN_REVIEW |
| ALLPHA-SEC-001 | Least privilege, owner/tenant isolation, default-deny privacy | Part XV §§72–76 | Security/privacy | 00, 02, 32, 37 | Negative auth, isolation, privacy and audit tests | NOT_VERIFIED |
| ALLPHA-DATA-001 | Database truth, versioned migrations, retention/deletion policy | Part XIV §§68–71 | Data/platform | 00, 02, domain phases | Migration, ownership, index/constraint and recovery evidence | NOT_VERIFIED |
| ALLPHA-API-001 | Typed/versioned APIs, stable errors, correlation IDs and idempotency as applicable | Parts IV–V; AGENTS.md | API/platform | 00, 01, domain phases | Contract tests and documented compatibility policy | IN_REVIEW |
| ALLPHA-AI-001 | All AI calls use canonical AI Gateway/Model Router; budgets and permissions enforced | Parts VI–IX | AI platform | 09–11, 36 | Router policy, usage/cost tests, secret scan, trace evidence | NOT_VERIFIED |
| ALLPHA-SPATIAL-001 | Asset storage presence is not publication approval; only authorized published manifests are public | Part XI §§46–53; AGENTS.md | Spatial/asset governance | 22–24 | Provenance/license, checksum, moderation, API and renderer/device QA | NOT_VERIFIED |
| ALLPHA-NFR-001 | Reliability, performance, accessibility and localization are acceptance concerns | Part XX §§86–90 | Architecture/QA | 00, relevant phases, 36–37 | Defined targets and test/device evidence | IN_REVIEW |

## 2. Canonical 82-domain inventory and proposed phase mapping

Domain names and responsibilities below follow Master PRD Part IV §14. Phase numbers are proposed mapping against Phase Plan v1.1.0 and remain subject to ADR-0001 where the roadmap conflicts.

| Domain ID | Canonical PRD domain | Primary responsibility (PRD summary) | Proposed phase owner(s) | Status |
|---|---|---|---|---|
| DOM-01 | Human Identity | Profile, preferences, locale, consent, account lifecycle and privacy | 03; foundation 02 | NOT_VERIFIED |
| DOM-02 | AI Agent Identity | Agent identity, owner link, visibility, status, versions and public profile | 05 | NOT_VERIFIED |
| DOM-03 | Agent Persona | Tone, behavior, objectives, style, disclosure and boundaries | 05–06 | NOT_VERIFIED |
| DOM-04 | Agent Memory | Memory scope, retention, provenance, write/retrieval policy and deletion | 08 | NOT_VERIFIED |
| DOM-05 | Agent Skills | Reusable skills, schemas, versions, tests, dependencies and publication | 06 | NOT_VERIFIED |
| DOM-06 | Agent Capability | Declared actions/tools, runtime-authorized per action | 05–06, 10 | NOT_VERIFIED |
| DOM-07 | Agent Passport | Owner-approved identity/capability disclosure, versions and terms | 05 | NOT_VERIFIED |
| DOM-08 | Interest Ontology | Normalized interests, topics, categories and semantic relationships | 04, 17 | NOT_VERIFIED |
| DOM-09 | Interest Graph | Permitted user/Agent interest relationships | 04, 17 | NOT_VERIFIED |
| DOM-10 | Passion Graph | Creator/topic affinity with sensitive-inference safeguards | 04, 17 | NOT_VERIFIED |
| DOM-11 | Habit Graph | Approved interaction patterns with user controls | 04, 17, 33 | NOT_VERIFIED |
| DOM-12 | Goal Graph | Goals, milestones, dependencies and progress | 12, 19 | NOT_VERIFIED |
| DOM-13 | Context Graph | Scoped, provenance-aware, expiring task/session context | 08–11 | NOT_VERIFIED |
| DOM-14 | Social Graph | Follow, block, connection and visibility relationships | 04 | NOT_VERIFIED |
| DOM-15 | Relationship Graph | Human–Agent, Agent–Agent and account relationships/permissions | 04–05, 18 | NOT_VERIFIED |
| DOM-16 | Community Graph | Community/member/role/content relationships | 19 | NOT_VERIFIED |
| DOM-17 | Content Graph | Authorship, media, topics, replies, references and engagement | 13–17 | NOT_VERIFIED |
| DOM-18 | Knowledge Graph | Entities, facts, relationships, source/provenance/confidence | 07–08 | NOT_VERIFIED |
| DOM-19 | Reputation Graph | Validated use/quality/safety signals and anti-sybil controls | 12, 32–33 | NOT_VERIFIED |
| DOM-20 | Agent Discovery | Public Agent search by capability, category, version and policy-safe signals | 17, 28 | NOT_VERIFIED |
| DOM-21 | Content Ingestion | Validate, parse, moderate, index and version uploads | 07, 13 | NOT_VERIFIED |
| DOM-22 | Feed Engine | Eligible paginated feed and ranking | 14 | NOT_VERIFIED |
| DOM-23 | Reels Engine | Short-video processing, playback, captions, visibility and recommendations | 15 | NOT_VERIFIED |
| DOM-24 | Stories Engine | Temporary content, audience, expiration and deletion | 16 | NOT_VERIFIED |
| DOM-25 | Live Engine | Live session lifecycle, roles, participant state and authorization | 25–27 | NOT_VERIFIED |
| DOM-26 | AI Live Engine | Agent runtime, voice, tools, presentation and character animation in live session | 24–26 | NOT_VERIFIED |
| DOM-27 | AI Capsule Engine | Structured capsules with sources, visibility and versions | 13 | NOT_VERIFIED |
| DOM-28 | Recommendation Engine | Rank eligible content/Agent/world by relevance, diversity, safety and controls | 14, 17 | NOT_VERIFIED |
| DOM-29 | Personalization Engine | Personalization from allowed signals with reset/disable controls | 04, 17, 33 | NOT_VERIFIED |
| DOM-30 | Search / Explore Engine | Cross-domain search for users, Agents, content, worlds and listings | 17 | NOT_VERIFIED |
| DOM-31 | Trend Engine | Emerging topics with spam/manipulation defenses | 17 | NOT_VERIFIED |
| DOM-32 | Social Interaction | Reactions, comments, mentions, shares, saves, reports and permissions | 14–16 | NOT_VERIFIED |
| DOM-33 | Messaging / DM | Conversations, participants, attachments, delivery/read state and retention | 18 | NOT_VERIFIED |
| DOM-34 | Community Engine | Community, membership, roles, moderation, content and events | 19 | NOT_VERIFIED |
| DOM-35 | Collaboration Engine | Shared spaces, co-editing, annotations, presence and access control | 19 | NOT_VERIFIED |
| DOM-36 | Mission Engine | Objectives, tasks, milestones, verification and reward hooks | 12, 19 | NOT_VERIFIED |
| DOM-37 | Agent Catalog | Public Agent versions, capabilities, terms and entitlement references | 28 | NOT_VERIFIED |
| DOM-38 | Marketplace | Listings, discovery, purchase rights, listing state and policies | 28–29 | NOT_VERIFIED |
| DOM-39 | Commerce Engine | Orders, payment references, refunds, settlement and transaction integrity | 29–30 | NOT_VERIFIED |
| DOM-40 | Economy | AI Credits, quota units, promotional credits and ledger operations | 30 | NOT_VERIFIED |
| DOM-41 | Creator Economy | Eligible usage, rewards/revenue, settlement, reversals and reports | 29–30 | NOT_VERIFIED |
| DOM-42 | Event Engine | Schedule, registration, attendance, linked sessions and lifecycle | 27 | NOT_VERIFIED |
| DOM-43 | Agent World | Permitted Agent presence, movement, spawn and interaction scope | 23–24 | NOT_VERIFIED |
| DOM-44 | Universe Engine | Universe/Galaxy topology, world registry and navigation hierarchy | 21 | NOT_VERIFIED |
| DOM-45 | District Engine | District/zones/roads/landmarks/buildings/plazas and spatial rules | 21, 23 | NOT_VERIFIED |
| DOM-46 | Booth / Tenant Engine | Booth identity/placement, tenant, catalog, interaction and access | 23, 29 | NOT_VERIFIED |
| DOM-47 | Tenant Leasing & Billing | Lease terms, tenant entitlement, billing schedule and expiry | 29–30 | NOT_VERIFIED |
| DOM-48 | World / Scene Schema | Validated declarative scene data and schema compatibility | 21–23 | NOT_VERIFIED |
| DOM-49 | Theme Engine | Theme definitions, versions, visual variants and publishing lifecycle | 22 | NOT_VERIFIED |
| DOM-50 | World Builder | Authoring, preview, validation, version comparison, publish and rollback | 22–23 | NOT_VERIFIED |
| DOM-51 | Theme Marketplace | Theme listings, licensing, entitlement, versions and purchases | 22, 28–29 | NOT_VERIFIED |
| DOM-52 | Agent Simulation Engine | Bounded character/Agent simulation; no permission bypass | 23–24 | NOT_VERIFIED |
| DOM-53 | Encounter Engine | Proximity, interaction invitations, eligibility and anti-spam | 23 | NOT_VERIFIED |
| DOM-54 | Presence Engine | Online/session/spatial presence with expiry and privacy | 18, 23, 26 | NOT_VERIFIED |
| DOM-55 | Realtime World Engine | Synchronize positions and multi-client world interactions | 23, 26 | NOT_VERIFIED |
| DOM-56 | World Stream | Progressive scene/asset/state loading by device/network budget | 23 | NOT_VERIFIED |
| DOM-57 | Notification Engine | In-app/push/email routing, preferences, deduplication and delivery | 20 | NOT_VERIFIED |
| DOM-58 | Analytics | Privacy-safe product/business metrics and access controls | 33 | NOT_VERIFIED |
| DOM-59 | Policy Engine | Rules for actions, data release, providers and publication | 02, 09, 32 | NOT_VERIFIED |
| DOM-60 | Permission Engine | Actor/action/resource/context authorization with safe reason codes | 02, cross-domain | NOT_VERIFIED |
| DOM-61 | Risk Engine | Risk signals and throttle/step-up/review/deny decisions | 32, 34 | NOT_VERIFIED |
| DOM-62 | Human Approval Engine | Approvals for sensitive tools, publishing, sharing and high-cost work | 06, 22, 32, 34 | NOT_VERIFIED |
| DOM-63 | Audit Ledger | Sensitive actions and financial/governance event integrity and retention | 02, 29–30, 34 | NOT_VERIFIED |
| DOM-64 | Trust & Safety | Reports, abuse, enforcement, appeals and incident workflows | 32 | NOT_VERIFIED |
| DOM-65 | Moderation | Moderation of content, Agents, skills, listings, ads and live content | 22, 31–32 | NOT_VERIFIED |
| DOM-66 | Privacy | Consent, purpose, export, deletion, retention, visibility and disclosures | 02–03, 08, 32 | NOT_VERIFIED |
| DOM-67 | Security | Architecture, auth, secrets, isolation, threat model and incidents | 00–02, 32, 36–37 | NOT_VERIFIED |
| DOM-68 | Identity Verification | Verification evidence for applicable feature/risk level | 32, 34 | NOT_VERIFIED |
| DOM-69 | Anti-Impersonation | Detect/review/enforce misleading identity claims | 32 | NOT_VERIFIED |
| DOM-70 | Anti-Fraud | Payment, credit, reward, marketplace and usage abuse detection | 29–32 | NOT_VERIFIED |
| DOM-71 | Agent Interoperability | Controlled Agent exchange with explicit protocols/data scopes | 35 | NOT_VERIFIED |
| DOM-72 | Agent API / Protocol | Versioned API/tool contracts, auth, quotas, errors and compatibility | 01, 35 | NOT_VERIFIED |
| DOM-73 | Subscription / Billing | Plans, invoices, renewals, expiry, cancellation, refunds and reconciliation | 30 | NOT_VERIFIED |
| DOM-74 | Revenue Engine | Pricing, attribution, platform fees, margin and eligible revenue rules | 29–31, 33 | NOT_VERIFIED |
| DOM-75 | Entitlement Engine | Server-side rights from plan, purchase, policy, role and limits | 28–30 | NOT_VERIFIED |
| DOM-76 | Feature Flag Engine | Rollout, experiments and emergency kill switches with audit | 01, 34, 36 | NOT_VERIFIED |
| DOM-77 | Configuration Engine | Validated global/tenant/feature config with versioning | 01, 34 | NOT_VERIFIED |
| DOM-78 | Super Admin Control Plane | Privileged operations across users, assets, billing and incidents | 34 | NOT_VERIFIED |
| DOM-79 | Developer Platform | API apps, OAuth, credentials, webhooks, integrations and docs | 35 | NOT_VERIFIED |
| DOM-80 | Observability | Logs, metrics, traces, alerts, SLOs and diagnostics | 01, 36 | NOT_VERIFIED |
| DOM-81 | Evaluation Engine | Model/Agent/retrieval/workflow/privacy/animation/safety evaluation | 12, 36–37 | NOT_VERIFIED |
| DOM-82 | E2E Test / QA Engine | Repeatable cross-domain regression, device/network matrix and evidence | 36–37 | NOT_VERIFIED |

## 3. Phase-level acceptance map

| Phase | Acceptance focus | Minimum evidence | Status |
|---|---|---|---|
| 00 | Contract, RTM, domain ownership, dependencies, ADR/risk and delivery governance | Reviewed docs, conflict decision, baseline inspection, signed phase report | IN_PROGRESS |
| 01 | New deployable mobile + web + API thin slice | Build/deploy/health evidence, secret scan, CI | NOT_VERIFIED |
| 02 | Auth, authorization and tenant isolation | Auth flows, RLS/policy tests, negative access tests, migration evidence | NOT_VERIFIED |
| 03–20 | Identity, Agent/AI, social/content/collaboration/notifications | Per-phase vertical-slice UI/API/data/security/tests/evidence | NOT_VERIFIED |
| 21–24 | Spatial model, GLB/theme lifecycle, renderer, avatars/animation | Manifest/API/license/moderation and device/visual QA evidence | NOT_VERIFIED |
| 25–31 | Live/events/marketplace/commerce/billing/ads | Real integration and financial/media lifecycle tests | NOT_VERIFIED |
| 32–36 | Trust, analytics, admin, developer platform and operations | Authorization/audit, analytics lineage, SLO/alert/security evidence | NOT_VERIFIED |
| 37 | Final cross-domain release gate | E2E, security regression, device/browser matrix, rollback and production evidence | NOT_VERIFIED |

## 4. Evidence row template

For each requirement, append or link:
- implementation commit/PR;
- files/modules/API/schema/migration;
- exact test command and pass/fail/skipped;
- security/privacy scenario;
- UI/device evidence when applicable;
- environment classification (test/mock/sandbox/staging/production);
- reviewer and date;
- known gaps and next action.

Never change `NOT_VERIFIED` to `VERIFIED` without the above evidence.
