# ADR-0001: Native Client Stack — React Native + Expo
- **Status:** Accepted
- **Date:** 2026-10-13
- **Scope:** ENG-P01, native Android/iOS in `apps/client`
- **Decision owner:** Product owner (explicit approval)

## Context
The Master PRD requires a native mobile app with secure credential storage, platform lifecycle behavior, and future camera/microphone/notification/3D adapters. `apps/client` previously contained only a README. ENG-P01 must add a buildable native slice without replacing Web/API apps.

## Options
1. React Native + Expo prebuild: TypeScript, generated native Android/iOS projects, native modules, lower bootstrap overhead.
2. React Native bare: direct native project ownership with more initial maintenance.
3. Flutter: cross-platform native support but a separate Dart/tooling stack.

## Decision
Use **React Native + Expo with native prebuild**. This is a native Android/iOS app, not a PWA. Commit source/configuration; CI generates native projects and validates builds. Business truth and privileged writes remain in the canonical FastAPI/Postgres backend. Persist mobile auth through platform secure storage. Only public Supabase publishable configuration may be bundled.

## Consequences
- Aligns TypeScript tooling with Web without duplicating domain logic.
- CI validates platform generation/build separately; JS bundle alone is not native-build evidence.
- Physical-device testing, store signing, push credentials, camera/microphone permissions, WebRTC and 3D performance remain feature-specific acceptance checks.

## Rollback
Decision is isolated to `apps/client`; API contracts and other app boundaries remain unchanged. Do not move business logic into the mobile app during a stack migration.
