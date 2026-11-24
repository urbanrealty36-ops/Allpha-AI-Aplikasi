# Content Media Worker Deployment and Activation

## Worker ownership

Image processing and video/audio transcode are intentionally separate from the Agent Runtime shared worker. The shared worker image is resource-constrained and delegates malware scanning to its remote scanner contract; it must not silently gain a local ClamAV daemon or a second media engine.

- Image derivatives: `apps/api/Dockerfile.media-worker` → `allpha-content-media-worker` → `content_media_worker.MediaWorker`
- Video/audio transcode dispatch: `apps/api/Dockerfile.transcode-worker` → `allpha-content-transcode-worker` → `content_transcode_worker.TranscodeWorker`
- Both consume the existing `content_media` lifecycle queue and service-only Postgres RPCs. The transcode provider callback, not the dispatch worker, owns final readiness promotion.

## Fail-closed activation

Both images default their feature flag to `false`. They exit successfully and remain inactive unless explicitly enabled.

Image worker requires:

- `ALLPHA_CONTENT_MEDIA_WORKER_ENABLED=true`
- `ALLPHA_CLAMAV_ENABLED=true`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` or server-only `SUPABASE_SECRET_KEY`
- `CLAMAV_HOST` (and optional `CLAMAV_PORT`, default 3310)
- `ALLPHA_DOCUMENT_SCANNER_ID=clamav-local`
- `ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION`
- `ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION`

Video/audio transcode worker requires:

- `ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED=true`
- `ALLPHA_CLAMAV_ENABLED=true`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` or server-only `SUPABASE_SECRET_KEY`
- `CLAMAV_HOST` (and optional `CLAMAV_PORT`)
- `ALLPHA_DOCUMENT_SCANNER_ID=clamav-local`
- `ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION`
- `ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `ALLPHA_CLOUDINARY_CALLBACK_URL` using HTTPS

Invalid boolean values or missing required configuration stop startup. Both workers use the shared `media_scanner.scan_media_bytes` adapter, which checks the exact pinned ClamAV engine and signature with `zVERSION` before each `INSTREAM` scan; missing pins, identity drift, timeout or non-clean verdict never promote media. Do not pass Supabase service credentials to Cloudinary. Do not set either feature flag true until the scanner endpoint, provider credentials, callback route/domain and callback signature validation are configured and verified.

## Current production state

At the latest Railway environment inspection, only the API, shared Agent Runtime/Workflow/Knowledge host, social graph outbox worker, Web and Super Admin services exist. The dedicated image and transcode worker services are not deployed. The shared worker has no ClamAV host, Cloudinary credentials or media worker feature flags. Therefore the TUS upload API can safely reserve, receive, verify and queue an object, but a media row will not reach `ready` until these dedicated workers are provisioned and configured.

Do not create idle/failing worker services or invent Cloudinary/ClamAV credentials. Provision the existing Dockerfiles as separate Railway services after the actual external endpoints and secrets are available. No new database is required.
