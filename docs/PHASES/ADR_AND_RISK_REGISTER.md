# ADR and Risk Register — Allpha

**Status:** Initial register derived from Master PRD v3.0.0, AGENTS.md and Phase Plan v1.1.0. Draft entries are not approved decisions.

## 1. ADR index

| ADR | Decision topic | Status | Blocking scope |
|---|---|---|---|
| ADR-0001 | Separate product-roadmap and engineering-execution namespaces with an explicit crosswalk | PRODUCT OWNER APPROVED — ENGINEERING LEAD APPROVAL PENDING | Final canonical crosswalk and phase status/check-off rules |
| ADR-0002 | Native cross-platform mobile stack and 3D/WebRTC capability spike | OPEN | Phase 01 native foundation and later spatial/live integration |
| ADR-0003 | Web framework and component implementation standard | OPEN | Phase 01 web foundation |
| ADR-0004 | Queue/worker and durable workflow persistence semantics | OPEN | Phase 01 platform contracts; Phase 07–11 production execution |
| ADR-0005 | Live media SFU/TURN, recording and transcoding architecture | OPEN | Phase 25–26 |
| ADR-0006 | Voice runtime, streaming contract and timestamp/viseme synchronization | OPEN | Phase 24–26 |
| ADR-0007 | Embedding/reranking providers and capability registry | OPEN | Phase 07–09 |
| ADR-0008 | Self-hosted inference capacity, GPU economics and routing policy | OPEN | Phase 09–10 and cost operations |
| ADR-0009 | 3D generation provider adapters and licensing policy | OPEN | Phase 22 asset acquisition/publishing |
| ADR-0010 | Object storage, CDN, signed URL and egress strategy | OPEN | Phase 01/22/23 |
| ADR-0011 | Free/Premium/Enterprise quota and pricing values | OPEN | Phase 09, 30–31 |
| ADR-0012 | Creator reward formula, settlement, cash-out and legal policy | OPEN | Phase 12, 29–30 |
| ADR-0013 | Data retention/deletion SLA by classification | OPEN | Phase 02–03, 07–08, 18 and 32 |
| ADR-0014 | Device performance profiles, frame/load and asset budgets | OPEN | Phase 22–24 |
| ADR-0015 | SLOs, backup RPO/RTO and production capacity | OPEN | Phase 01, 36–37 |
| ADR-0016 | Final 14-category asset compatibility schema | OPEN — taxonomy keys are specified; detailed required metadata remains to approve | Phase 22–24 |

## 2. ADR-0001 — Phase roadmap reconciliation

- **Status:** `accepted` by explicit Product Owner override on 2026-10-13. Engineering Lead review is deferred and remains a non-blocking follow-up; this record does not impersonate or fabricate an Engineering Lead approval.
- **Decision proposed and approved by Product Owner:** Option 3 — maintain two explicit namespaces:
  1. **PRD Product Phase (`PRD-P00`–`PRD-P24`):** the product roadmap and feature/acceptance framing in Master PRD v3.0.0 Part XVIII §82.
  2. **Engineering Execution Phase (`ENG-P00`–`ENG-P37`):** the detailed implementation sequence in Phase Master Plan v1.1.0.
- **Approval record:** Product Owner explicitly directed “Approve aja udah, langsung ke phase selanjutnya” on 2026-10-13. This is recorded as the authorized Product Owner decision to accept Option 3 and proceed. No Engineering Lead decision is claimed.
- **Context:** Master PRD v3.0.0 Part XVIII §82 lists Phase 00–24. The Phase Master Plan v1.1.0 defines Phase 00–37 with a more detailed and differently ordered implementation sequence. `AGENTS.md` states that phase plans must not silently override the PRD and requires reconciliation before later phase numbering is treated as canonical.
- **Decision scope:** This decision separates namespaces and requires a reviewed crosswalk. It does **not** rewrite PRD requirements, declare all 38 engineering phases complete/canonical product phases, approve application architecture choices, or authorize dependent phase status changes without evidence.
- **Crosswalk:** [Phase Roadmap Crosswalk](./PHASE_ROADMAP_CROSSWALK.md). The initial mapping is a proposed routing aid; exact requirement-level mapping and dependencies remain subject to engineering review.
- **Accepted rules:**
  - Use `PRD-Pnn` when referring to product roadmap phases and acceptance framing.
  - Use `ENG-Pnn` when referring to execution plan tasks, commits, PRs, and engineering phase status.
  - Do not refer to a bare phase number in governance decisions or cross-phase evidence when the namespace could be ambiguous.
  - Keep the PRD's 00–24 roadmap unchanged until a separate approved decision explicitly amends it.
  - Phase completion statuses remain those specified by the PRD; a phase-plan checklist or successful CI alone does not establish acceptance.
- **Trade-offs:** This preserves the product roadmap while retaining detailed engineering sequencing, at the cost of maintaining crosswalk references and explicit namespace labels.
- **Consequence:** ADR-0001 is accepted by Product Owner direction so execution can proceed. Engineering Lead review of detailed crosswalk mappings remains an open quality task, not a reason to block the ENG-P01 foundation work. Phase 00's separate evidence gate is still open; starting ENG-P01 does not mean Phase 00 has passed.
- **Owner/approvers:** Product Owner (decision accepted 2026-10-13); Engineering Lead (detailed crosswalk review deferred, no decision fabricated).
- **Evidence:** Master PRD Part XVIII §82; `AGENTS.md` §§1 and 4; Phase Plan v1.1.0 §§1–4; Product Owner instruction dated 2026-10-13.
- **Migration/rollback:** Preserve PRD phase IDs and historical links. If later Engineering Lead review identifies mapping defects, revise the crosswalk through a follow-up decision/change record; do not rewrite Master PRD implicitly.
- **Follow-up:** Engineering Lead reviews detailed mapping quality when available; execution of the ENG-P01 thin slice proceeds meanwhile.

## 3. Risk register

| Risk ID | Risk | Impact | Mitigation / exit condition | Owner | Status |
|---|---|---|---|---|---|
| R-001 | Phase roadmap namespace/crosswalk approval pending | Ambiguous phase authority and incorrect completion claims | Engineering Lead review/approval; finalize crosswalk; update references and evidence | Product owner + engineering lead | IN_PROGRESS |
| R-002 | Repository has GLB acquisition/audit tooling but no verified app vertical slice | Mistakenly treating asset tooling as product implementation | Inspect source tree/CI and explicitly separate tooling from product capability | Engineering | IN_PROGRESS |
| R-003 | Architecture choices are open | Premature stack/provider decisions create rework | Approve relevant ADR before dependent production implementation | Architecture owner TBD | OPEN |
| R-004 | 82-domain scope and many integrations | Delivery complexity, duplicated engines and hidden dependencies | Enforce ownership map, dependency graph and vertical slices | Product/engineering | OPEN |
| R-005 | GLB provenance/licensing/compatibility uncertainty | Unauthorized or unusable assets reach product | Per-asset provenance/license, validation, moderation and renderer QA | Asset governance owner TBD | OPEN |
| R-006 | Private data or Agent memory leakage | Privacy/security incident | Default-deny, query-time filters, authorization and negative-path tests | Security owner TBD | OPEN |
| R-007 | False completion from docs/build/UI-only evidence | Unverified capability shipped | Completion contract and evidence registry | QA/release owner TBD | OPEN |
| R-008 | Missing environment/CI baseline evidence | Phase acceptance cannot be reproduced | Capture branch/head, tree, workflow and test status before Phase 01 | Engineering | OPEN |
| R-009 | Production migrations without recovery proof | Data loss/outage | Versioned migration, fresh/upgrade tests, backup and rollback/forward repair | Data owner TBD | OPEN |
| R-010 | Secrets or sensitive data enter repo/logs | Credential compromise | Secret scanning, redaction, least privilege and rotation | Security owner TBD | OPEN |

## 4. ADR template

Copy to `docs/architecture/adr/ADR-NNNN-short-title.md`:

```markdown
# ADR-NNNN: <title>
- Status: proposed | accepted | rejected | superseded
- Date:
- Owners:
- Approver:
- Related requirements:
- Related phases:

## Context and problem
## Constraints and requirements
## Options considered
## Trade-offs
## Decision
## Consequences
## Security and privacy impact
## Data/API compatibility
## Migration and rollback
## Validation/evidence
## Supersedes / superseded by
```

## 5. Risk record template

```markdown
# R-NNN: <risk title>
- Status: open | in_progress | blocked | accepted | closed
- Owner:
- Affected requirement IDs:
- Affected phases:
- Evidence:
- Impact and likelihood:
- Mitigation:
- Exit condition:
- Approval / date:
```


## Product Owner execution directive — 2026-10-13

The Product Owner explicitly directed acceptance of ADR-0001 and immediate commencement of the next engineering phase. This is the decision evidence for the `accepted` status. Engineering Lead review is not represented as complete; the remaining crosswalk review is tracked as follow-up. The independent Phase 00 evidence gate remains open and is not conflated with ADR acceptance.
