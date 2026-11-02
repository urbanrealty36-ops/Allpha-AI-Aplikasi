# API background workers

## Social Graph Outbox

Entry point: `allpha-social-graph-outbox-worker` (registered in `pyproject.toml`). The worker uses the canonical `social_graph_events` outbox and the existing FastAPI/Supabase service-role boundary; it does not create a second workflow engine.

### Production worker service configuration
- Create/attach a dedicated Railway worker process in the existing Allpha production project (same repository and `apps/api` root; do not create another database).
- Build using `apps/api/Dockerfile`; override the container start command with `allpha-social-graph-outbox-worker`.
- Configure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (or the already-supported server secret alias `SUPABASE_SECRET_KEY`) from the existing Railway environment. Never copy credentials into the repository or client apps.
- Optional settings: `SOCIAL_OUTBOX_BATCH_SIZE` (default 25, max 100), `SOCIAL_OUTBOX_LEASE_SECONDS` (default 45, range 10–300), `SOCIAL_OUTBOX_POLL_SECONDS` (default 2), `SOCIAL_OUTBOX_MAX_ATTEMPTS` (default 8, max 20), and `LOG_LEVEL`.
- Use one or more replicas safely: claims use `FOR UPDATE SKIP LOCKED`, each claim has a unique lease token, and the downstream effect ledger is unique by event ID.

### Effect and retry contract
- The committed downstream effect invalidates feed snapshots belonging to the event actor and target participants. This is the correct cache invalidation for follow/block/mute changes; interest events invalidate the owner's personalized snapshots.
- `apply_social_graph_event_effect` verifies the live lease and atomically inserts the unique effect record, invalidates the affected snapshots, and marks the event processed in one database transaction.
- Failures are returned to `pending` with bounded exponential backoff; the configured maximum attempt count transitions the event to `dead`. Expired processing leases can be reclaimed.
- Do not manually mark an event processed. The worker only uses the claim/apply/fail RPCs.

### Activation and evidence
The worker code, CLI entry point, SQL functions, grants, and schema are committed and the database migration has been applied. The worker is **not operationally active** until the dedicated Railway worker process is configured with the existing production credentials and its runtime logs/queue effects are observed. This implementation did not create a new environment, send test events, or activate production consumption.