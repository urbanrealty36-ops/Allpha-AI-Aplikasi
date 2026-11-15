# ADR-WP10-001 — Live Experience media provider and session transport

- **Status:** PROPOSED — NOT APPROVED
- **Date:** 2026-11-15
- **Scope:** WP-10 / ENG-P25 / ENG-P26 (Live Experience, realtime streaming, voice, camera and Stage)
- **Decision owners:** Product Owner, Platform Architecture, Security/Privacy, Finance/Operations
- **Implementation owner:** Live Experience Engineering
- **Approval required before:** provider provisioning, live media token issuance, recording activation, provider webhook activation, production media traffic or paid egress.

## Context and PRD requirements

The Master PRD v3.1 defines Live Experience as a realtime environment for Humans and AI Agents to present, teach, discuss, interview, pitch, analyze documents, co-create and interact in a Stage. The Stage is not complete without media transport, synchronized Stage state, document pipeline, AI runtime, voice, animation, permissions, participant UX, failure recovery and usage accounting.

The canonical lifecycle is:

`draft → scheduled → lobby → live → paused → ending → ended`

Alternate outcomes: `cancelled`, `failed`, `terminated_by_moderation`.

The v3.1 Social/Cinema Addendum additionally requires: `planned`, `scheduled`, `preparing`, `live`, `paused/reconnecting`, `ended`, `replay processing`, `replay ready`, `cancelled`, `failed`, and `moderation stopped`. These vocabularies must be reconciled in the canonical state model before implementation; do not silently collapse or rename them.

Required media architecture:
- FastAPI authorizes session, participant role, entitlement, moderation and media actions.
- FastAPI issues short-lived, session- and role-scoped media credentials; secrets remain server-side.
- WebRTC signaling negotiates connections.
- An SFU distributes media for multi-participant sessions.
- STUN/TURN supports network traversal.
- Adaptive bitrate, reconnect and participant recovery are required.
- Recording/transcoding runs in isolated media workers and follows explicit consent/retention.
- Realtime events synchronize participant/Stage state, slide state, reactions and animation cues.
- FastAPI must not proxy media frames.
- Provider/media failure must produce an explicit UI state and recovery path.

The existing ADR-WP04-002 selects Cloudinary for asynchronous uploaded video/audio transformations only. It does **not** select a WebRTC SFU, TURN service, live recording provider, or Live Stage transport provider.

## Decision statement

No Live media provider is selected by this proposal. The decision remains blocked pending Product Owner, Security/Privacy and Finance/Operations approval of provider, deployment model, region, egress, recording and retention.

The provider adapter must be replaceable and must not become the source of truth for Allpha session state, participants, roles, permissions, moderation, credits or audit.

## Candidate approaches for evaluation

| Candidate approach | Evaluation focus | Main trade-offs to validate |
|---|---|---|
| Managed WebRTC platform (e.g. LiveKit Cloud, Agora, Daily) | Fastest path to multi-region SFU, SDK support, TURN and operational SLAs | Vendor lock-in, per-participant-minute/egress pricing, data region, recording cost, webhook/security model |
| Self-hosted LiveKit SFU + managed TURN | Greater control over deployment, data locality and media topology | SRE ownership, scaling, TURN bandwidth, upgrades, observability, incident response and on-call burden |
| Self-hosted mediasoup SFU + managed TURN | Fine-grained control and custom orchestration | More integration and operational engineering; SDK, recording and moderation pipeline must be assembled |
| Hybrid managed SFU with Allpha-owned control plane and recording pipeline | Keeps Allpha authorization and durable lifecycle canonical while delegating transport | Cross-provider correlation, recording storage/retention, webhook integrity and cost attribution |

The examples are candidates only, not endorsements or claims of current vendor capabilities. Current pricing, supported regions, data-processing terms, SDK/platform support, recording behavior and SLA must be researched and verified before approval.

## Required architecture boundaries

1. **Canonical control plane:** `apps/api` owns Live Session, participant membership, role grants, host/co-host/speaker/guest/viewer/moderator permissions, state transitions, moderation, recording consent, audit and usage policy.
2. **Transport adapter:** a provider adapter exposes create-room, issue-token, revoke-token, participant events, publish/subscribe state, end-room and provider health. Provider IDs are external references, not canonical Allpha IDs.
3. **Credential lifecycle:** media credentials are short-lived, least-privilege, session-bound, participant-bound, permission-bound and revocable. No provider secret or service credential reaches Web/Native clients.
4. **Realtime synchronization:** Supabase Realtime or the existing canonical event layer may distribute authorized Stage-state changes; it is not the media transport and cannot authorize a state transition.
5. **Media transport:** WebRTC + SFU + STUN/TURN. Media packets never traverse ordinary FastAPI request handlers.
6. **Recording/replay:** recording requires explicit consent and disclosure, bounded retention, moderation, private canonical Storage, signed access and deletion propagation. Provider recording callbacks are signed, replay-protected and correlated to session/recording attempts.
7. **AI Agent participation:** Agent presence, voice, tools, memory/Knowledge access and autonomous actions require owner policy, explicit scopes, disclosure, budget and current session permission. Human takeover must revoke the relevant autonomous writes.
8. **Cost/usage:** session minutes, participant minutes, egress, recording, transcription and AI usage are metered separately against approved policy. No guessed cost or credit debit.
9. **Failure behavior:** provider unavailable, token expired, reconnecting, degraded network, host disconnect, recording failure, moderation stop and ended states are explicit. No UI may show live success or viewer counts without provider-confirmed evidence.
10. **Privacy:** camera/mic/screen/document permissions are independent. A viewer token cannot publish; a speaker token cannot manage host state. Recording and observer roles require explicit disclosure.

## State-model reconciliation required

Before schema/API implementation, record one canonical state machine and mapping from both PRD vocabularies. Minimum semantic states:
- preparation: draft/planned/scheduled/preparing/lobby;
- active: live;
- interrupted: paused/reconnecting;
- termination: ending;
- terminal: ended/cancelled/failed/terminated_by_moderation;
- replay: replay_processing/replay_ready.

This list is a reconciliation proposal, not an approved replacement for the PRD states.

## Acceptance gates

- Approved provider, deployment model, region, egress and recording/retention policy.
- Versioned FastAPI contracts for session create/schedule/start/join/pause/resume/end, participant role changes, independent media permissions, moderation stop, chat, recording consent and replay access.
- Durable schema and transactional state-transition RPCs with optimistic versioning/idempotency.
- Provider adapter contract and authenticated, replay-protected webhooks.
- Web and Native Stage adapters using the existing reference `LiveExperienceStage` composition and design tokens.
- Short-lived role-scoped tokens; host, co-host, speaker, guest, viewer and moderator authorization.
- Reconnect, network degradation, provider outage, host disconnect, token expiry, moderation stop and recording failure recovery.
- Recording consent, retention/deletion, private storage and audit evidence.
- Usage metering and budget enforcement without fabricated counts or charges.
- Focused isolated integration tests and Web/Android/iOS acceptance before any production activation.

## Current repository evidence and known gap

At the 2026-11-15 source inspection:
- Web `/live` mounts the reference-derived `LiveExperienceStage` with `liveStateAvailable=false`.
- No canonical Live Session FastAPI router or media-session contract exists in the current `apps/api` source tree.
- The target Stage component is shorter than the reference source and is not byte-identical; it has intentional fail-closed adaptations, but full structural/class/interaction parity is not verified.
- Live Stage media controls are disabled or return explicit unavailable states; no fake live viewers, chat, likes, media session or successful start is fabricated.
- No Live provider is configured or selected by this ADR.

## Approval checklist

- [ ] Product Owner approves provider/deployment model.
- [ ] Security/Privacy approves data region, token scopes, consent, recording and retention.
- [ ] Finance/Operations approves pricing, egress/recording budget, limits and incident ownership.
- [ ] Architecture approves state-model reconciliation and provider adapter contract.
- [ ] Only after approval: implement WP-10 / ENG-P25/P26 source vertical slice and record evidence in the fixed phase plan.

## Rollback

Disable new session creation and provider token issuance; revoke active provider credentials where supported; transition affected sessions to an explicit failed/ended state through the canonical control plane; preserve audit and consent evidence; retain private recordings until the approved retention/deletion process runs. Do not delete source uploads or claim provider-side erasure without evidence.
