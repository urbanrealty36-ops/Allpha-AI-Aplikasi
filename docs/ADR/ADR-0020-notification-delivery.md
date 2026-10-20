# ADR-0020: Notification Delivery and Native Push Transport

- **Status:** Accepted for the initial Expo Push Service adapter; native device delivery remains gated on EAS project configuration and real token registration.
- **Date:** 2026-10-20
- **Scope:** ENG-P20 notification preferences, transactional event producers, durable push dispatch, device registration, retries and receipts.
- **Decision owner:** Product Owner.

## Context

The Master PRD requires notification preferences, deduplicated event delivery, durable bounded work, retry/recovery, native notifications and clear separation between in-app inbox persistence and device delivery. The canonical mobile client is Expo React Native. The existing production project has a dedicated Railway Cron Worker pattern and one canonical Supabase database; no new database or staging environment is needed.

## Options

1. Expo Push Service using Expo push tokens. Lowest integration overhead for the existing Expo client; requires a configured EAS project identifier in the native app, a development/production build with expo-notifications, and device permission/token registration.
2. Direct FCM/APNs delivery. Provides direct provider control but requires Firebase/APNs credentials, platform configuration and credential rotation.
3. Provider-neutral inbox only. Preserves durable in-app notifications but does not provide remote push.

## Proposed decision

Use an adapter boundary in the canonical API worker and initially implement an Expo Push Service adapter, because the current native client is built on Expo. Keep dispatch fail-closed: it is disabled unless ALLPHA_NOTIFICATION_WORKER_ENABLED=true, ALLPHA_NOTIFICATION_PUSH_ENABLED=true, and ALLPHA_NOTIFICATION_PUSH_PROVIDER=expo. The worker must not claim delivery until the Expo receipt is checked. A device token is private data and is never returned in API responses or written to logs.

The user explicitly requested full native push implementation for the canonical Expo React Native client. Expo Push Service is selected as the first reversible transport; direct FCM/APNs can replace it behind the same adapter if required later. The native plugin and package dependency are now present, but apps/client/app.json does not contain an EAS project ID and the current build environment has no EXPO_PUBLIC_EAS_PROJECT_ID. Production push has zero registered devices today. The production Cron Worker is deployed with the Expo adapter enabled safely because no device tokens exist. A production-only EAS build workflow is now in .github/workflows/native-production-build.yml and requires the GitHub Actions secret EXPO_TOKEN plus the repository variable EXPO_PUBLIC_EAS_PROJECT_ID. Actual delivery still requires those values, Expo/EAS Android FCM and iOS APNs credentials, a production native build, and real users to grant notification permission and register tokens.

## Data and lifecycle

- Message notifications are produced transactionally from the canonical public.messages insert trigger and deduplicated by (user_id, event_key).
- public.user_settings.notification_preferences remains the only preference registry.
- public.notification_devices stores owner-scoped Expo tokens with soft disable.
- public.notification_push_deliveries stores per-notification/per-device state, leases, attempts, ticket IDs and receipt outcomes.
- The API owns authenticated preference/device management; the worker alone dispatches through the provider.
- No message content is copied into push body; push payload contains only a generic message notice and safe route identifiers.

## Rollout and rollback

The schema is additive and uses no data deletion. Disable dispatch with ALLPHA_NOTIFICATION_PUSH_ENABLED=false or ALLPHA_NOTIFICATION_WORKER_ENABLED=false; pending rows remain durable. Rollback of code must not drop the new tables or delete queued rows. A forward repair is preferred after the producer trigger is enabled because notification rows already emitted are legitimate user data.

## Acceptance evidence

Before setting ENG-P20 to acceptance_passed, verify:
- native app EAS project ID, push plugin, build and real token registration on Android/iOS;
- explicit provider approval and production worker configuration;
- message-to-inbox event with deduplication and user preference suppression;
- worker lease/retry/receipt behavior and device-token revocation;
- authenticated Web and Native inbox/preferences journeys against production without fabricated business records.
