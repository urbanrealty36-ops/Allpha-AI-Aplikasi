# ADR-WP04-002 — Managed video/audio processing provider

- Status: ACCEPTED FOR IMPLEMENTATION; ACCOUNT ACTIVATION PENDING
- Date: 2026-11-03
- Scope: WP-04 content media lifecycle only

## Context

Allpha retains Supabase Storage as the canonical private source for uploaded originals and metadata. Video/audio transcoding is asynchronous and must not set media ready until provider processing has completed, callbacks are authenticated, derivatives have been copied into canonical Storage, and the database completion transaction succeeds.

## Decision

Use Cloudinary Image & Video APIs as the managed transformation provider for video and audio.

- Audio is submitted using Cloudinary's `video` resource type (Cloudinary documentation explicitly describes MP3/WAV/FLAC as video asset type for audio transformations).
- Uploads are server-to-server from the isolated media worker using Cloudinary delivery type `authenticated`; both originals and all eager derivatives require signed delivery URLs. Provider credentials never reach clients.
- Callback derivative URLs must use the configured Cloudinary HTTPS host and authenticated video delivery path; the callback is signed, and the API copies derivatives immediately into the private canonical Supabase bucket. Cloudinary URLs are never returned to clients.
- Generate bounded, pre-approved eager derivatives asynchronously; use an eager notification URL.
- Configure webhook trigger signing as `legacy_hmac` until EdDSA v2 public-key verification is separately implemented. Validate `X-Cld-Timestamp` freshness and HMAC signature against the exact raw request body plus timestamp using constant-time comparison.
- Callback must correlate the provider public ID, provider asset ID, media ID, lifecycle job ID and immutable processing attempt. It must reject stale, duplicate, mismatched or failed events.
- Derivative URLs are fetched only from the exact Cloudinary HTTPS delivery host derived from the configured cloud name, then copied into the original private Supabase bucket under deterministic derivative paths. No arbitrary callback URL may be fetched.
- Only an atomic database RPC may set media ready and complete its job, after checking the live lease, source record, clean provider moderation/scan result, expected derivatives, and callback event idempotency.
- Provider delivery URLs are not the canonical public media references. Allpha's publication authorization, visibility, moderation and signed access remain controlled by FastAPI/Supabase.

## Consequences and operational gates

- Required secrets: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`. Configure them only in the isolated worker and API secret stores.
- Configure callback URL to the FastAPI API project and set the webhook auth scheme to `legacy_hmac`.
- Review Cloudinary plan limits, data processing region, retention, backup/deletion behavior, transformation quotas, and cost before production activation.
- No provider account, credentials, webhook, plan, region, or production activation is claimed by this ADR.
- If the account is not configured, jobs remain pending/failed and media remains private processing/unavailable; never fake a ready state.

## Alternatives considered

- AWS Elemental MediaConvert: capable managed media processing but requires additional AWS object storage, IAM, event delivery and cross-storage lifecycle wiring.
- Self-hosted FFmpeg: offers control but introduces codec patching, isolation, scaling and operations burden; not selected for this managed-provider requirement.
- Mux: strong video workflow but does not meet the one-provider video+audio transformation preference as cleanly as Cloudinary.

## Rollback

Disable provider job dispatch and webhook processing; leave affected media private and non-ready. Do not delete originals. Retry only after provider configuration and job correlation have been reconciled. A provider switch requires a new ADR and versioned adapter contract.
