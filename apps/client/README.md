# Allpha Client

Primary end-user client boundary. Native Android/iOS is the target; web client code currently lives in `apps/web` and will be migrated or shared here without duplicating business logic.

- All domain operations use the typed backend API.
- Shared API contracts belong in `packages/contracts`.
- Keep platform-specific camera, microphone, push notification, secure storage, and 3D capabilities behind adapters.
- GLB assets are discovered from the backend asset catalog/manifest and loaded by the shared renderer; do not hard-code private Storage URLs.

Initial implementation step: select and bootstrap the native runtime, then connect auth/profile and the asset catalog to real APIs.
