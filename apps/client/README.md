# Allpha Native Client (Android + iOS)
React Native + Expo prebuild; native application, not a PWA.

## Configuration
Set local, uncommitted values:
- `EXPO_PUBLIC_API_BASE_URL`: canonical FastAPI origin. Production/EAS builds must use `https://api.allpha.web.id`. Android emulator default for local development: `http://10.0.2.2:8000`; iOS simulator default: `http://localhost:8000`. Physical devices need a reachable LAN/HTTPS origin. The production app falls back to the canonical API domain when this variable is unset.
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


## Native authentication return links

The Native Client contains handlers for the custom-scheme routes `allpha://auth/callback` (email verification) and `allpha://auth/recovery` (password recovery). The existing HTTPS callback remains the default until the custom-scheme URLs are added to the canonical Supabase Auth **Redirect URLs** allow-list.

After the two URLs are allow-listed, configure these EAS environment variables for the approved existing Allpha EAS project:

- `EXPO_PUBLIC_NATIVE_AUTH_REDIRECT_URL=allpha://auth/callback`
- `EXPO_PUBLIC_NATIVE_RECOVERY_REDIRECT_URL=allpha://auth/recovery`

Do not set these values before the Supabase allow-list is updated. They are public redirect URLs, not secrets. The native callback exchanges the PKCE authorization code through Supabase Auth, validates the resulting session through the existing FastAPI identity bootstrap, and uses `/v1/auth/revoke` after a successful password update. Real device callback verification remains part of the ENG-P01/ENG-P02 acceptance evidence.
