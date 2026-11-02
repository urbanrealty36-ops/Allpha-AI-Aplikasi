# Native Android & iOS export/build

This guide covers reproducible JavaScript export and EAS native builds for apps/client. Signing, store submission, and publication are separate release activities.

## Prerequisites
- Node.js compatible with Expo SDK 54 and the repository lockfile; install dependencies without regenerating the lockfile.
- Expo account with access to the approved Allpha EAS project; authenticate with `npx eas-cli login`.
- Existing EAS project linkage in app.json/app.config must refer to the approved project. Do not create a second project.
- Configure EXPO_PUBLIC_API_BASE_URL, EXPO_PUBLIC_SUPABASE_URL, and EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY through EAS environment variables or ignored local .env. These are public client values; never expose service-role keys or provider secrets.

## JavaScript bundle export
Run from apps/client:
```bash
npm run export:android
npm run export:ios
```
These run expo export for the selected platform and produce JS/assets output. They do not create a signed APK, AAB, or IPA.

## EAS native builds
```bash
npx eas-cli login
npx eas-cli project:info
npm run build:android
npm run build:ios
npm run build:all
```
Profiles are development, preview, and production in eas.json. Production Android uses AAB; iOS targets physical devices.

### Android credentials
EAS-managed credentials are recommended. The first production build may ask EAS to generate/configure an Android upload keystore. Confirm package name com.allpha.universe, Play Console ownership, upload-key custody, and recovery/rotation. Never commit keystore files, passwords, or exported credential JSON.

### iOS credentials
A physical-device/App Store build requires an Apple Developer Program team, distribution certificate, provisioning profile for com.allpha.universe, and App Store Connect access. EAS can manage certificates/profiles after an authorized Apple account is connected. Automated submission additionally requires an App Store Connect API key (issuer ID, key ID, private key) stored in EAS credentials/secrets. Never commit the .p8 private key.

## Submission (deferred)
The submit.production entry is configuration only. Submission requires approved store metadata, privacy declarations, screenshots, review accounts, release notes, and store credentials. No submission or publication is performed by these commands.

## Operational safeguards
- Keep signing credentials in EAS-managed secure storage or an approved secret manager.
- Never place Supabase service-role keys in app config or EXPO_PUBLIC variables.
- Record EAS build ID, commit SHA, profile, platform, and artifact checksum for accepted builds.
- JS export is not native-build evidence; EAS build is not publication evidence.

## Current EAS project-link status

The current app.json contains the Android package and iOS bundle identifier but does not yet contain extra.eas.projectId. Therefore the build scripts are prepared, but an EAS native build cannot be started safely until the existing approved Allpha EAS project ID is supplied/linked. Do not run project initialization in a way that creates a second project. Once the existing project ID is confirmed, add expo.extra.eas.projectId to app.json and verify it with npx eas-cli project:info. No EAS project ID or signing credential is inferred or fabricated here.
