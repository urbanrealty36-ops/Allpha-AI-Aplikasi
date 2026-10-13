# Allpha Native Client (Android + iOS)
React Native + Expo prebuild; native application, not a PWA.

## Configuration
Set local, uncommitted values:
- `EXPO_PUBLIC_API_BASE_URL`: canonical FastAPI origin. Android emulator default: `http://10.0.2.2:8000`; iOS simulator default: `http://localhost:8000`. Physical devices need a reachable LAN/HTTPS origin.
- `EXPO_PUBLIC_SUPABASE_URL`
- `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (publishable key only).

All `EXPO_PUBLIC_*` values are public. Never bundle service-role, database, JWT signing, AI-provider or payment secrets.

## Run
```bash
npm install
npm run typecheck
npm test
npx expo prebuild --platform android && npx expo run:android
# macOS + Xcode:
npx expo prebuild --platform ios && npx expo run:ios
```

The first slice includes API health, email sign-in/sign-up, secure session persistence and authenticated `GET /v1/me`. Settings editing, social graph, push, WebRTC and 3D renderer remain in their owning phases.
