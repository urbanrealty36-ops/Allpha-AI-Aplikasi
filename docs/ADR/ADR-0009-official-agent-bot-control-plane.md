# ADR-0009: Official Allpha Agent Bot Control Plane

- **Status:** Accepted for source implementation; live integration remains deferred.
- **Date:** 2026-10-16
- **Owners:** Product Owner / Platform Engineering
- **Scope:** Official Allpha bot roster, Human Agent Identity Skill selection, and Super Admin lifecycle controls.

## Context

Allpha needs a selectable catalog of Agent Skill blueprints for Human-owned Agents and a separately governed roster of Official Allpha bot candidates for platform seeding. The external reference repository advertises 500+ Agent projects/use cases, while its current `agents/` tree contains 21 self-contained implementation folders. A catalog of 500 use-case blueprints must not be described as 500 executable agents.

The Master PRD requires explicit Agent ownership, one canonical Agent Runtime, runtime authorization outside model output, strict tool schemas, bounded execution, and Super Admin privileged operations with scopes and audit. It also requires actual GLB provenance/manifest mapping before claiming a character asset is ready for rendering.

## Decision

1. The canonical backend `apps/api` exposes a versioned, searchable Skill catalog. Catalog membership is descriptive and grants no tool permissions.
2. Human Agent creation on Web and Native records the selected catalog key/version and a suggested character role in the Agent persona. This is a selection contract only; it is not proof that a Skill was instantiated in `agent_skills`, executed, or published.
3. The official-bot roster is an operator-only control-plane overlay keyed by catalog Skill. It is not a second Agent identity system and does not replace `ai_agents`, `agent_ownerships`, `agent_skills`, Agent Runtime, or the runtime-policy registry.
   - ENG-P05 platform identity provisioning is a privileged adapter over the same canonical `ai_agents` and `agent_ownerships` records. The backend uses the server-only `ALLPHA_PLATFORM_OWNER_USER_ID` configuration, which must identify a real dedicated platform service-account user in `auth.users`; clients cannot submit or override this owner. `provision_official_agent_identity` is callable only by `service_role`, locks the roster row, and atomically creates a draft Agent identity plus its canonical owner relationship. It is idempotent when the existing identity still matches the configured owner. This configuration/account is not yet confirmed, and the source-only migration is not applied.
4. Roster provisioning creates draft candidates only. A roster row becomes eligible for activation only after a canonical Agent identity, approved runtime policy, and backend-verified character asset are linked. No operator click can mark a GLB verified.
5. High-risk lifecycle actions require the existing `platform:capabilities.review.high_risk` scope and durable operator audit. Stop/isolate lifecycle changes are recorded, but a runtime dispatcher is not considered implemented merely because roster status changed.
6. Official bots use supervised autonomy by default. Runtime execution must remain bounded by the canonical policy, permissions, rate/cost limits, task deadlines, cancellation, and owner/platform intent. No arbitrary upstream code is imported or executed by the catalog.
7. All source migrations remain unapplied until the approved isolated integration window. No production DB mutation is part of this decision.

## Consequences

- The current source increment provides a 500-entry metadata catalog, Web/Native selection UI, and a Super Admin draft-roster/lifecycle API surface.
- 21 catalog entries reference named upstream repository examples; the remaining curated blueprints are taxonomy-based use-case definitions, not verbatim upstream projects.
- No real 3D asset is asserted available: character asset keys remain unmapped/unverified until reconciled with the canonical asset registry.
- The roster can be populated only after the migration is applied to an approved isolated target. The current implementation does not create 500 canonical Agent identities, start autonomous runtime workers, publish GLB assets, or prove 500 bots active.
- Remaining implementation includes canonical system-owned Agent provisioning, Skill blueprint instantiation/versioning, asset registry verification, runtime stop/isolation enforcement, official-bot task scheduling/observability, and cross-client integration acceptance.

## Alternatives rejected

- Copying and executing upstream agent code directly: rejected because it bypasses the canonical runtime/policy boundary and upstream project-specific dependencies/secrets.
- Treating 500 catalog rows as 500 running bots: rejected because catalog entries are not executable handlers or durable Agent identities.
- Giving the Super Admin client service-role access or direct database writes: rejected; all privileged changes pass through FastAPI.
- Activating a bot without verified 3D asset/runtime policy: rejected; readiness is fail-closed.
