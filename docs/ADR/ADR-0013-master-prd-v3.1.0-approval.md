# ADR-0013 — Master PRD v3.1.0 approval and canonical precedence

- **Status:** Accepted by Product Owner
- **Date:** 2026-11-02
- **Decision owner:** Product Owner, Allpha Universe
- **Scope:** Master PRD document control only; all product, security, privacy, architecture and phase invariants remain in force.

## Context

The canonical repository path `docs/PRD/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE.md` contains the consolidated v3.1.0 document, preserving the original v3.0.0 baseline and appending the v3.1.0 AI Social Network, Creator Economy and AI Cinema addendum. AGENTS.md previously named version 3.0.0 as current. The Product Owner explicitly approved v3.1.0 as the current governing specification on 2026-11-02.

## Decision

1. The content currently stored at the canonical repository path is the authoritative Master PRD and is version 3.1.0.
2. The original v3.0.0 baseline remains preserved verbatim within the consolidated document; v3.1.0 extends it and does not erase the original spatial/3D requirements.
3. AGENTS.md must identify v3.1.0 as the current version and cite this ADR.
4. The fixed phase plan remains the sole operational engineering phase plan. This ADR does not create or renumber phases.
5. This decision does not waive evidence requirements, authorize fabricated data, weaken security/privacy boundaries, or permit unverified runtime/production claims.

## Consequences

All implementation work must trace against the consolidated v3.1.0 PRD. Where a phase plan or legacy document conflicts with the current PRD, record the conflict and resolve it through an explicit decision rather than silently changing product behavior.
