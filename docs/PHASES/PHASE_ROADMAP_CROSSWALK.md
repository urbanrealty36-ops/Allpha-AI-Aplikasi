# Phase Roadmap Crosswalk — Allpha

- **Status:** Draft mapping for ADR-0001; Product Owner approved the two-namespace approach on 2026-10-13. Engineering Lead approval is pending.
- **Authority:** Master PRD v3.0.0 Part XVIII §82 remains the product roadmap source. Phase Master Plan v1.1.0 is the detailed engineering execution sequence, not a silent replacement for the PRD.
- **Purpose:** Provide a readable initial mapping between PRD Product Phases (`PRD-P00`–`PRD-P24`) and Engineering Execution Phases (`ENG-P00`–`ENG-P37`).
- **Important:** This is a high-level routing proposal, not proof that a mapped feature is implemented or accepted. The detailed mapping must be reviewed against each requirement, acceptance scenario, owner, and dependency before ADR-0001 can be marked accepted.

## Namespace rules

- Write `PRD-Pnn` for a phase defined in Master PRD §82.
- Write `ENG-Pnn` for a phase defined in Phase Master Plan v1.1.0.
- Avoid bare phase numbers in decisions, issues, PRs, release notes, and evidence where the namespace could be ambiguous.
- Preserve the Master PRD's Phase 00–24 IDs. Any change to that roadmap requires a separate explicit, approved source change.
- Phase status must use the Master PRD completion vocabulary: `not_started`, `in_progress`, `blocked`, `implemented`, `integration_verified`, `acceptance_passed`, `production_verified`.

## Initial mapping

| PRD phase | Master PRD product scope | Proposed engineering phase(s) | Mapping rationale / review notes |
|---|---|---|---|
| PRD-P00 | Product, architecture and delivery contract | ENG-P00; cross-cutting ENG-P01, ENG-P02, ENG-P34, ENG-P36 | Contract, governance, security baseline, environment and delivery evidence. ENG-P00 remains in progress. |
| PRD-P01 | Identity, account and human control center | ENG-P02, ENG-P03, ENG-P20, ENG-P32, ENG-P34 | Identity/profile/privacy lifecycle spans identity, notification, trust and admin surfaces; validate exact ownership. |
| PRD-P02 | Agent identity, persona and passport | ENG-P05, ENG-P06 | Agent identity/ownership and capability/publishing controls. |
| PRD-P03 | API boundary, policy, isolation and audit | ENG-P01, ENG-P02, ENG-P32, ENG-P34, ENG-P35, ENG-P36 | Cross-cutting foundation and security/governance; do not imply one phase owns all controls. |
| PRD-P04 | AI Gateway, Model Router and usage | ENG-P09, ENG-P10, ENG-P36 | Routing, runtime use, metering and operational cost signals. |
| PRD-P05 | Agent runtime, orchestration and resume | ENG-P10, ENG-P11, ENG-P36 | Runtime lifecycle, durable workflow, retry/resume and observability. |
| PRD-P06 | Memory, knowledge and hybrid retrieval | ENG-P07, ENG-P08, ENG-P09, ENG-P32 | Ingestion/retrieval/privacy controls; exact dependency order requires review. |
| PRD-P07 | Skill Builder and Visual Workflow Studio | ENG-P06, ENG-P11 | Skill contracts and durable workflow authoring/execution. |
| PRD-P08 | Agent learning and AI Challenge | ENG-P07, ENG-P12, ENG-P36 | Learning/evaluation capability and evidence. |
| PRD-P09 | Social Graph and Community | ENG-P04, ENG-P17, ENG-P19, ENG-P20, ENG-P32 | Relationship graph, discovery, community, notifications and moderation dependencies. |
| PRD-P10 | Content, Feed, Reels, Stories and Capsule | ENG-P13, ENG-P14, ENG-P15, ENG-P16, ENG-P17, ENG-P32 | Content creation/consumption/discovery and trust controls. |
| PRD-P11 | Search, Explore, Recommendations and Trends | ENG-P17, ENG-P33, ENG-P36 | Search/recommendation capability plus analytics/evaluation. |
| PRD-P12 | Messaging and Collaboration | ENG-P18, ENG-P19, ENG-P20, ENG-P32, ENG-P36 | Communication, shared workspace, notifications, moderation and reliability. |
| PRD-P13 | Theme, World Builder and Asset Pipeline | ENG-P22, ENG-P23, ENG-P32, ENG-P36 | Asset lifecycle and renderer integration with licensing/moderation/performance gates. |
| PRD-P14 | Universe, District, Zone and Booth | ENG-P21, ENG-P23, ENG-P29, ENG-P36 | Spatial hierarchy, world interaction, tenant/booth dependencies and runtime evidence. |
| PRD-P15 | Media Surfaces, Ads and District Content | ENG-P31, ENG-P32, ENG-P33, ENG-P34 | Ads inventory/governance, moderation, measurement and admin control. |
| PRD-P16 | AI Character and Animation | ENG-P24, ENG-P25, ENG-P26, ENG-P36 | Character/animation contracts used by spatial and live capabilities. |
| PRD-P17 | Live Streaming and Stage 3D | ENG-P25, ENG-P26, ENG-P27, ENG-P24, ENG-P36 | Stage/live session, streaming, events, AI character and operational controls. |
| PRD-P18 | Marketplace, Commerce, Billing and Credits | ENG-P28, ENG-P29, ENG-P30, ENG-P32, ENG-P34, ENG-P36 | Catalog/commerce/economy/billing, anti-fraud, admin reconciliation and operations. |
| PRD-P19 | Creator Economy, Reward and Missions | ENG-P12, ENG-P29, ENG-P30, ENG-P32, ENG-P33 | Challenge/mission, creator commerce/reward, billing, fraud controls and analytics. |
| PRD-P20 | Developer Platform and Integrations | ENG-P35, ENG-P09, ENG-P32, ENG-P34, ENG-P36 | Public API/interoperability with AI routing, security, admin and observability. |
| PRD-P21 | Super Admin Control Plane | ENG-P34, ENG-P32, ENG-P36 | Privileged operational UI, governance and audit/observability. |
| PRD-P22 | Trust, Safety and Privacy Hardening | ENG-P02, ENG-P32, ENG-P34, ENG-P36, ENG-P37 | Controls are foundational and cross-cutting; hardening/regression continues through release. |
| PRD-P23 | Observability, evaluation and quality | ENG-P01, ENG-P09, ENG-P11, ENG-P12, ENG-P36, ENG-P37 | Observability/evaluation begins with foundational vertical slices and is consolidated in operations/release. |
| PRD-P24 | Full System Integration and Release Readiness | ENG-P37, with evidence from all prior ENG phases | Final cross-domain gate; it must validate completed capability, not become a feature implementation dumping ground. |

## Review checklist for Engineering Lead

- [ ] Confirm the two namespace definitions and the no-silent-override rule.
- [ ] Review each PRD-to-ENG mapping against the full phase acceptance criteria and dependency graph.
- [ ] Review cross-cutting ownership (security, privacy, moderation, analytics, observability) and avoid implying a single phase contains all relevant work.
- [ ] Confirm phase references in issues/PRs/evidence use explicit `PRD-Pnn` or `ENG-Pnn` labels.
- [ ] Confirm that the PRD remains unchanged unless separately approved.
- [ ] Record reviewer role, decision, date, and requested changes in ADR-0001.

## Approval log

| Role | Decision | Date | Evidence |
|---|---|---|---|
| Product Owner | Approved Option 3: separate namespaces with explicit crosswalk | 2026-10-13 | Explicit approval in project conversation; role supplied by requester |
| Engineering Lead | Pending | — | Approval evidence not yet supplied |

## Exit condition

ADR-0001 may be marked `accepted` only after Engineering Lead approval is recorded, the mapping review checklist is completed or remaining limitations are explicitly accepted, and the ADR/crosswalk references are read-back verified. Phase 00 still requires its separate evidence-based exit review.
