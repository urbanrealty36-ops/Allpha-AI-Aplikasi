# ADR-0018: Scheduled Stories Cleanup Worker

- **Status:** Accepted
- **Date:** 2026-10-19
- **Scope:** ENG-P16 Stories/Moments retention and media derivative cleanup
- **Decision owner:** Product Owner (approval recorded in project conversation)

## Context

The current Stories API archives expired Stories and attempts private Storage cleanup while a Story endpoint is being accessed. This is not a reliable retention mechanism: a quiet application may not execute cleanup, and interrupted or failed Storage deletion must remain retryable. The Master PRD sections 18, 57, 83 and 86 require bounded durable work, expiry, deletion/derivative cleanup, safe retries and observable recovery.

The canonical source of truth remains `content_items` plus `content_media` in the existing Allpha Supabase project. A second Story registry, database or queue is prohibited for this scope.

## Decision

Use a **dedicated Railway Cron Worker** in the existing production Railway project, sourced from `urbanrealty36-ops/Allpha-AI-Aplikasi` branch `main`, rooted at `/apps/api`, running `python -m allpha_api.stories_cleanup_worker`. The production schedule is every 15 minutes (`*/15 * * * *`). It is a one-shot process per invocation, not an always-running worker and not part of the API request process.

The worker:
1. Uses the existing server-side Supabase configuration through Railway service-variable references; secrets are not copied into source code or clients.
2. Invokes the existing canonical Story expiry lifecycle, then sweeps archived/deleted Story media left in recoverable states.
3. Uses compare-and-set status changes before deleting media, treats Storage 404 as already deleted, and removes `content_media` metadata only after Storage deletion is confirmed or the object is already absent.
4. Leaves metadata in `deleting` when deletion fails so the next scheduled run can retry.
5. Uses bounded batch sizes, non-sensitive structured counters, and a non-zero process exit for fatal database/configuration errors. Per-object Storage failures are recorded and retried on a later run.
6. Does not create Stories, fixtures, fake business data, a new table, or a new database.

## Operational bounds

- Default batch limit: 100 media-bearing archived/deleted Stories per run; configurable only within 1–200.
- Schedule: every 15 minutes, with no in-process unbounded retry loop.
- Each invocation exits after one bounded pass; Railway owns scheduling and execution lifecycle.
- If a run fails, the next scheduled invocation retries retained work. Operators can inspect Railway deployment logs and counters.

## Security and privacy

- The worker has server-only Supabase credentials through Railway variable references.
- No public endpoint is exposed.
- Storage paths are taken from canonical database metadata and URL-encoded as object paths.
- Only Story records in `archived` or `deleted` lifecycle states are swept by the recovery scan.
- The existing API remains the owner of Story creation, moderation, publication, and authorization.

## Consequences and risks

- Cleanup latency is up to approximately one schedule interval under normal conditions, plus queue/backlog time.
- This ADR does not establish a final retention SLA for every media class; that remains a broader PRD decision.
- Cron execution is at-least-once. Compare-and-set transitions and idempotent object deletion make repeated runs safe.
- Production deployment is considered verified only after the actual Railway Cron service configuration and a successful live run are observed.

## Validation

Required automated coverage includes successful expiry delegation, archived/deleted-only selection, failed Storage retry retention, Storage 404 idempotency, metadata deletion only after Storage success, bounded batch settings, strict configuration gating and fatal dependency error behavior. Real authenticated user journeys and Android/iOS device acceptance remain separate ENG-P16 acceptance gates.
