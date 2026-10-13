# ENG-P03 — Human Identity

**Status:** IN_PROGRESS — implementation committed; CI and live authenticated user-flow acceptance pending.  
**Canonical data/auth:** Supabase AllphaAiAplikasi-db, project ref dvdziauyvuhcnqhrrvww.  
**Execution policy:** direct commits on main, per AGENTS.md.

## Delivered vertical slice

- Browser Supabase Auth client with persistent session, sign-in, sign-up and sign-out.
- Authenticated UI loads the real user identity through FastAPI and reads/writes settings through authenticated endpoints; no mock identity/profile data is used.
- Profile UI: username, display name, avatar URL, bio, profile visibility, locale and account status.
- User settings UI: theme preference, notification preferences, discoverability preference.
- Account deactivation request records a state transition request; it does not delete the account or revoke the session.
- API: GET/PATCH /v1/me/profile, GET/PATCH /v1/me/settings, GET /v1/me/consents, POST /v1/me/deactivation-request.
- Settings and consent tables use RLS. User-scoped bearer tokens are forwarded by the API; no service-role key is used by the browser or these routes.
- Public browser config is passed as NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY; only publishable credentials belong there. Backend uses SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY plus caller token for PostgREST.

## Schema and migration evidence

Applied to the canonical project:
- eng_p03_human_identity_preferences_and_consent
- eng_p03_single_source_profile_visibility

Tables/fields added:
- profiles.locale, profiles.account_status
- user_settings with theme, notification and discoverability preferences
- user_consents for versioned consent records
- Auth/profile triggers provision user settings idempotently.

The live schema was inspected before changing it. The existing profiles.visibility remains the single source of truth for profile visibility; it is not duplicated in the user settings JSON.

## Scope boundaries and known gaps

- Avatar is currently an external URL field; authenticated upload to Supabase Storage is not part of this slice.
- Notification settings persist, but notification delivery is not yet implemented.
- Discoverability preference persists, but a public profile/discovery service is not yet implemented.
- Consent history can be read, but consent capture must be wired to actual published Terms and Privacy documents before claiming legal consent acceptance.
- Account deactivation is a recorded request, not hard deletion, session revocation, or complete lifecycle automation.
- Password reset, email-change, MFA, account export and hard deletion remain follow-up work unless required by the Master PRD acceptance checklist.
- Real signup/signin/profile/settings flow against a dedicated test account, email confirmation behavior, RLS negative tests and deployment env verification still need to be exercised. Do not call this production-verified yet.

## Verification

- API tests are added in apps/api/tests/test_human_identity.py.
- Check current run: https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions
- Security Advisor was checked after the schema change and returned no lints at the time of inspection.
- The Supabase migration history may assign timestamps different from the intended local migration filename; repository filenames must be reconciled to the recorded live versions before declaring migration history fully reproducible.
