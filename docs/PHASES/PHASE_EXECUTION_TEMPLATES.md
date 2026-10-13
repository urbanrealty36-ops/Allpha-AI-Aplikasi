# Phase Execution, Test, Evidence and Release Templates

Use these templates for every phase. Do not fill a result as passed until it has actually been observed. Keep mock/test-only evidence distinct from real integrations.

## 1. Phase execution plan

```markdown
# Phase NN — <canonical title>
- Status: not_started | in_progress | blocked | implemented | integration_verified | acceptance_passed | production_verified
- Baseline PRD / phase plan:
- Owner / reviewer:
- Dependencies and their evidence:
- Scope:
- Non-goals:
- Open ADRs / blockers:
- Risks:

## Requirement traceability
| Requirement ID | PRD section | Domain owner | Module/API/data/UI | Security/privacy | Tests | Evidence | Status |

## Acceptance criteria
| AC ID | Scenario / expected result | Test method | Evidence link | Pass/fail/blocked |

## Implementation plan
1. Inspect baseline and existing patterns.
2. Design schema/API/UI/security and failure behavior.
3. Implement the vertical slice.
4. Migrate safely if required.
5. Test success and negative/recovery paths.
6. Verify real integrations and UI/device behavior.
7. Capture evidence and update status board.

## Report
- Commit/PR:
- Tests run (exact commands and outcomes):
- Security/privacy checks:
- Integration target: test/mock/sandbox/staging/production
- Evidence:
- Known gaps:
- Reviewer and date:
- Next dependency/phase:
```

## 2. Test plan

```markdown
# Test Plan — Phase NN
- Requirement/AC IDs:
- Environment and dependency classification:
- Test data provenance (synthetic fixtures only in isolated test scope):
- Risks and threat scenarios:

| Test ID | Type | Scenario | Preconditions | Command/steps | Expected result | Actual result | Evidence | Status |
|---|---|---|---|---|---|---|---|---|

Required applicable coverage: unit; API/contract; integration; migration fresh-install and upgrade; authorization/tenant isolation; invalid/empty/unauthenticated/forbidden/not-found/conflict; timeout/retry/cancel/recovery; UI/accessibility/responsive; E2E/device/browser; regression/performance/security.
```

## 3. Evidence report

```markdown
# Evidence Report — Phase NN
- Commit/PR:
- Build/CI run:
- Requirement and acceptance IDs:
- Environment:
- Evidence owner/reviewer/date:

| Evidence ID | Requirement/AC | Artifact or URL | Exact command/scenario | Result | Environment | Reviewer |
|---|---|---|---|---|---|---|

- Migration evidence:
- API/authorization evidence:
- UI/device/browser evidence:
- Security/privacy evidence:
- Logs/traces/observability:
- Known limitations:
- Sign-off:
```

## 4. Release report

```markdown
# Release Report — <version>
- Immutable commit:
- Release candidate/build:
- Environment:
- Included phases/features and requirement IDs:
- Migration and compatibility status:
- Security/privacy review:
- E2E/device/browser matrix:
- Known issues and accepted risks:
- Monitoring/alerts and operational owner:
- Rollback/forward-repair plan:
- Backup/restore evidence:
- Release decision: GO | NO-GO
- Approver/date:
```

## 5. Change request

```markdown
# Requirement Change — CR-NNN
- Source/reason:
- Affected requirement IDs/PRD sections:
- Affected domains/phases:
- Behavioral/API/schema/UI/security changes:
- Backward compatibility and migration:
- Acceptance/test changes:
- ADR/risk updates:
- Decision/approver/date:
```
