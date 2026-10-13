# ADR and Risk Register — Allpha

**Status:** Initial register derived from Master PRD v3.0.0, AGENTS.md and Phase Plan v1.1.0. Draft entries are not approved decisions.

## 1. ADR index

| ADR | Decision topic | Status | Blocking scope |
|---|---|---|---|
| ADR-0001 | Canonical phase roadmap: Master PRD Phase 00–24 vs Phase Plan v1.1.0 Phase 00–37 | PROPOSED — approval required | Phase numbering/check-off after Phase 00; all dependent phase status claims |
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

- **Status:** PROPOSED; not approved.
- **Context:** Master PRD v3.0.0 Part XVIII §82 lists a Phase 00–24 roadmap. The current Phase Master Plan v1.1.0 defines Phase 00–37 and different titles/order for some phases. `AGENTS.md` explicitly says the PRD roadmap currently defines 00–24 and warns not to invent later phase numbering or claim it canonical without reconciliation.
- **Options:**
  1. Treat the Master PRD Phase 00–24 roadmap as canonical and revise the 00–37 plan to a mapped implementation sequence.
  2. Formally approve Phase Plan v1.1.0 as an expanded sequencing plan; retain PRD Phase 00–24 as product roadmap and publish an explicit crosswalk, with a reviewed PRD/AGENTS change if the canonical phase IDs are being amended.
  3. Maintain two phase namespaces (PRD product roadmap and engineering execution plan) with explicit crosswalk and no ambiguous phase IDs in issues/commits.
- **Trade-offs:** Option 1 maximizes PRD literal consistency but may lose detailed sequencing. Option 2 preserves current detailed execution plan but requires governance approval and source updates. Option 3 preserves both but adds coordination overhead.
- **Recommendation (not a decision):** Option 3 until the product owner explicitly approves whether phase IDs are shared or separately namespaced.
- **Consequence until approved:** Do not silently claim the Phase 00–37 IDs override PRD roadmap. Continue Phase 00 documentation and use document-qualified phase references. Dependent implementation phase status remains gated by the decision.
- **Owner/approver:** Product owner + engineering lead (names/approval not yet recorded).
- **Evidence:** Phase Plan v1.1.0 §§1–4; Master PRD Part XVIII §82; AGENTS.md §4.
- **Migration/rollback:** Update crosswalk, phase board, references and status only after approved decision; preserve prior versions and links.

## 3. Risk register

| Risk ID | Risk | Impact | Mitigation / exit condition | Owner | Status |
|---|---|---|---|---|---|
| R-001 | Phase roadmap conflict | Ambiguous phase authority and incorrect completion claims | Approve ADR-0001; publish crosswalk; update source docs | Product owner + engineering lead | BLOCKED |
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
