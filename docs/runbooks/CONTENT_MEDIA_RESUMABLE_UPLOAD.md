# Content Media — Resumable Supabase Storage Upload

## Ownership and security

FastAPI remains the business-logic and authorization boundary. A client never receives the Supabase service-role/secret key. The client first authenticates to FastAPI with its user access token. FastAPI verifies content ownership, validates the media contract, reserves the existing `content_media` row in `uploading` state, and asks Supabase Storage to create a short-lived signed upload token for one exact object path with `upsert=false`.

The signed upload token is scoped to the reserved bucket/object path and is returned to the authenticated client only for the TUS transport. The Supabase publishable/anon key is public application configuration, not a server credential. Do not log the signed token, TUS session URL or Authorization headers.

## API contract

1. Reserve or resume a media upload:

   `POST /v1/content/{content_id}/media/resumable`

   Requires a user bearer token and UUID `Idempotency-Key` header. JSON body:

   - `filename`
   - `media_type` (must be an existing allowed media MIME type)
   - `size_bytes` (must be within the existing content media limit)
   - `sha256` (lowercase SHA-256 hex calculated by the client)

   FastAPI verifies ownership and draft state, binds the idempotency key to owner/content/type/size/name/hash, creates or reuses the `content_media` reservation and returns the TUS endpoint, signed token, TUS metadata, and 6 MiB chunk size. Reusing a key for different file attributes is rejected.

2. Upload bytes using Supabase Storage TUS:

   - POST the returned `tus_endpoint` with `Tus-Resumable: 1.0.0`, `Upload-Length`, base64 `Upload-Metadata`, public `apikey`, and `x-signature` containing the short-lived signed upload token.
   - Persist the returned TUS `Location` URL on the client. Web stores it in localStorage; Native stores it in SecureStore.
   - HEAD the TUS URL to recover `Upload-Offset`, then PATCH sequential chunks with `Content-Type: application/offset+octet-stream` and the current offset. A network interruption leaves the upload URL available for a later resume.
   - If the TUS session is no longer available, call the reservation endpoint again to receive a fresh path-scoped token and create a new session. If the object already exists, do not overwrite it; call the completion endpoint.

3. Confirm and promote the object:

   `POST /v1/content/{content_id}/media/{media_id}/complete`

   FastAPI reads the reserved object through the server-only Storage credential, checks actual byte count, computes SHA-256, validates the media signature against the declared MIME type, and only then transitions the existing row from `uploading` to `uploaded`. The existing database-triggered media lifecycle and Railway image/transcode workers continue from that state. A client claim of completion alone never promotes the media.

## Current limits and recovery

- The current `content-media` bucket and API contract retain the existing 50 MiB per-file limit. TUS provides resumability within this configured limit; it does not yet enable multi-gigabyte feature-film files. Raising the limit requires a coordinated forward-only change to the Storage bucket configuration and existing database constraints, after checking the actual Supabase plan and recovery implications. Do not guess a higher limit.
- The upload reservation is stored in the existing `content_media` table; no new database or parallel media engine is created.
- Completion verification uses a bounded 300-second Storage request timeout and validates actual bytes before queue promotion.
- Web and Native persist one active Creator upload session per app instance. To resume after a process/page restart, reselect the same file. The session is matched by filename, size and SHA-256.
- A failed or incomplete upload remains in `uploading`; it is not shown as ready. Existing scan/transcode workers and creator media status remain authoritative.
- No live production upload has been performed as part of source/CI verification. Production readiness requires an actual signed TUS upload, server-side completion verification, scanner receipt and transcode completion through the deployed services.
