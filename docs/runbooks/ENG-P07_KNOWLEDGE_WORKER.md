# ENG-P07 Knowledge policy and ingestion worker operations

This runbook records the runtime contract. It does not create credentials, select an
external scanner/provider, approve an embedding tariff, or activate a worker.

## Canonical Knowledge policy provider

FastAPI and the Knowledge ingestion worker share the request-scoped policy resolver.
Configure the provider only after the canonical database RPC and its RLS/privilege
contract have been installed and reviewed:

- `ALLPHA_KNOWLEDGE_POLICY_FACTORY=allpha_api.supabase_knowledge_policy:build_provider`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (server/worker secret only; never expose to clients)

The adapter calls the service-only PostgREST RPC
`public.resolve_agent_knowledge_policy` with owner, Agent, audience, tenant, session
and purpose identities derived by the server. The RPC must return the strict snapshot
documented by `KnowledgePolicySnapshot`: policy and consent versions, grant version,
decision reference, exact source IDs, sensitivity and purpose allow-lists, active/
revoked/expiry result, and the echoed trusted scope. A missing function, malformed
response, stale/revoked decision or network error keeps ingestion and retrieval
unavailable. Generic `user_consents` records are not Knowledge authorization.

**Do not configure the factory against a guessed or substitute RPC.** The current
production catalog has no Knowledge-specific consent/source-grant RPC or tables.
ADR-0005 requires the physical contract and lifecycle review before activation.
The provider adapter is source-ready; the database contract remains deferred.

## Malware scanning

Choose exactly one real scanner mode and supply its actual deployment identity.

### Remote scanner
- `ALLPHA_DOCUMENT_SCANNER_URL` (HTTPS endpoint)
- `ALLPHA_DOCUMENT_SCANNER_API_KEY` (secret)
- `ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS` (exact hostname allow-list)
- `ALLPHA_DOCUMENT_SCANNER_ID`
- `ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION`
- `ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION`

The remote scanner must implement `allpha.document-scan.v1`, return a definitive
clean/malicious verdict, and echo the exact SHA-256 and pinned scanner/engine/
signature identity. DNS pinning, TLS hostname verification, redirect rejection,
response-size limits and strict receipt validation are enforced by the adapter.

### Local ClamAV worker image
- `ALLPHA_DOCUMENT_SCANNER_MODE=clamd`
- `ALLPHA_DOCUMENT_SCANNER_ID=clamav-local`
- `ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION` (exact output version from the deployed ClamAV binary)
- `ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION` (exact database/signature identity from the deployed ClamAV binary, formatted as `<database-version>/<database-timestamp>`)

The dedicated Knowledge worker image includes ClamAV and its daemon configuration.
Do not set this mode on an image that does not contain the scanner binary/daemon.
The worker startup and each scan require the configured engine/signature pins to
match the actual binary output exactly. Missing pins or runtime version drift keep
the source quarantined; an untrusted verdict is never converted to a clean receipt.
Pin values must be taken from the actual deployed image/daemon and must not be
copied from examples or guessed. A missing scanner remains unavailable and the
job follows the worker's retry/error classification.

## Embedding and vector indexing

The canonical embedding router requires the complete approved deployment profile:
`ALLPHA_EMBEDDING_BASE_URL`, `ALLPHA_EMBEDDING_API_KEY`,
`ALLPHA_EMBEDDING_PROVIDER_ID`, `ALLPHA_EMBEDDING_MODEL_ID`,
`ALLPHA_EMBEDDING_MODEL_VERSION`, `ALLPHA_EMBEDDING_DIMENSIONS`,
`ALLPHA_EMBEDDING_POLICY_ID`, `ALLPHA_EMBEDDING_POLICY_VERSION`,
`ALLPHA_EMBEDDING_POLICY_APPROVAL_REFERENCE`, `ALLPHA_EMBEDDING_PRICING_VERSION`,
`ALLPHA_EMBEDDING_COST_UNIT`, `ALLPHA_EMBEDDING_INPUT_COST_MICROUNITS_PER_TOKEN`,
`ALLPHA_EMBEDDING_MAX_INPUT_TOKENS`, `ALLPHA_EMBEDDING_MAX_COST_MICROUNITS`,
`ALLPHA_EMBEDDING_MAX_PROMPT_BYTES`, `ALLPHA_EMBEDDING_MAX_LATENCY_MS`,
`ALLPHA_EMBEDDING_ALLOWED_SENSITIVITIES`, `SUPABASE_URL`, and
`SUPABASE_SERVICE_ROLE_KEY`.

The active vector generation is supplied as
`ALLPHA_KNOWLEDGE_VECTOR_GENERATION_ID`. A generation is not ready until the
readiness RPC and atomic upsert RPC return matching receipts. Production currently
has pgvector 0.8.2 but no Knowledge vector table, generation registry, readiness/
upsert RPC, approved model profile, dimension, distance metric, index parameters
or active generation. Do not use sample values or enable hybrid retrieval until
ADR-0003/ADR-0004 decisions and review evidence exist.

## Operational invariants

- Clients use FastAPI only; no direct client writes to Knowledge tables or Storage.
- Uploaded originals remain private and quarantined until a definitive scanner
  receipt is persisted.
- Every job is owner/Agent/source-version scoped and lease fenced.
- Revocation must deny future retrieval before repository search and enqueue
  downstream derived-data invalidation.
- Never enable the Knowledge document or embedding consumer merely because its
  image builds. Confirm all required runtime settings and the exact Railway worker
  service configuration first.
