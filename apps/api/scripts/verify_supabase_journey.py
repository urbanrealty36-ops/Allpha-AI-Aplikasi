"""Real Supabase Auth -> FastAPI /v1/me -> logout integration smoke.

Required environment variables:
  SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, ALLPHA_API_BASE_URL,
  ALLPHA_E2E_TEST_EMAIL, ALLPHA_E2E_TEST_PASSWORD

Use a dedicated non-production test account. Never print credentials or tokens.
"""
from __future__ import annotations

import os
import sys

import httpx


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required integration environment variable is missing: {name}")
    return value


def main() -> int:
    supabase_url = required("SUPABASE_URL").rstrip("/")
    publishable_key = required("SUPABASE_PUBLISHABLE_KEY")
    api_base = required("ALLPHA_API_BASE_URL").rstrip("/")
    email = required("ALLPHA_E2E_TEST_EMAIL")
    password = required("ALLPHA_E2E_TEST_PASSWORD")
    timeout = httpx.Timeout(15.0, connect=5.0)
    with httpx.Client(timeout=timeout) as client:
        login = client.post(
            f"{supabase_url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": publishable_key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
        if login.status_code != 200:
            print(f"FAIL: Supabase sign-in returned HTTP {login.status_code}", file=sys.stderr)
            return 1
        session = login.json()
        access_token = session.get("access_token")
        if not access_token or not session.get("user", {}).get("id"):
            print("FAIL: Supabase sign-in did not return a valid user session", file=sys.stderr)
            return 1

        me = client.get(f"{api_base}/v1/me", headers={"Authorization": f"Bearer {access_token}"})
        if me.status_code != 200:
            print(f"FAIL: authenticated /v1/me returned HTTP {me.status_code}", file=sys.stderr)
            return 1
        body = me.json()
        if body.get("user", {}).get("id") != session["user"]["id"]:
            print("FAIL: /v1/me identity does not match the authenticated Supabase user", file=sys.stderr)
            return 1
        if "profile" not in body:
            print("FAIL: /v1/me response does not include profile contract", file=sys.stderr)
            return 1

        logout = client.post(
            f"{supabase_url}/auth/v1/logout",
            headers={"apikey": publishable_key, "Authorization": f"Bearer {access_token}"},
        )
        if logout.status_code not in (200, 204):
            print(f"FAIL: Supabase logout returned HTTP {logout.status_code}", file=sys.stderr)
            return 1
        after_logout = client.get(f"{api_base}/v1/me", headers={"Authorization": f"Bearer {access_token}"})
        if after_logout.status_code != 401:
            print(f"FAIL: /v1/me after logout returned HTTP {after_logout.status_code}, expected 401", file=sys.stderr)
            return 1

    print("PASS: Supabase sign-in, identity/profile API, logout, and revoked-session rejection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
