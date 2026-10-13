"""Read-only real integration checks for ENG-P02 tenant isolation.

This script must run only against a dedicated staging Supabase project and a
pre-provisioned staging organization. It performs reads plus deliberately
denied writes; it does not create or mutate business records.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

import httpx

CANONICAL_PROJECT_HOST = "dvdziauyvuhcnqhrrvww.supabase.co"


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required staging integration variable is missing: {name}")
    return value


def main() -> int:
    environment = required("ALLPHA_ENVIRONMENT").lower()
    supabase_url = required("SUPABASE_URL").rstrip("/")
    publishable_key = required("SUPABASE_PUBLISHABLE_KEY")
    api_base = required("ALLPHA_API_BASE_URL").rstrip("/")
    tenant_a_email = required("ALLPHA_TENANT_A_EMAIL")
    tenant_a_password = required("ALLPHA_TENANT_A_PASSWORD")
    tenant_b_email = required("ALLPHA_TENANT_B_EMAIL")
    tenant_b_password = required("ALLPHA_TENANT_B_PASSWORD")
    organization_id = required("ALLPHA_TENANT_A_ORG_ID")

    host = (urlparse(supabase_url).hostname or "").lower()
    if environment != "staging" or host == CANONICAL_PROJECT_HOST or not host.endswith(".supabase.co"):
        print(
            "FAIL: tenant-isolation integration is staging-only; refusing non-staging or canonical Supabase URL.",
            file=sys.stderr,
        )
        return 2

    timeout = httpx.Timeout(15.0, connect=5.0)
    with httpx.Client(timeout=timeout) as client:
        def sign_in(email: str, password: str) -> tuple[str, str]:
            response = client.post(
                f"{supabase_url}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": publishable_key, "Content-Type": "application/json"},
                json={"email": email, "password": password},
            )
            if response.status_code != 200:
                raise RuntimeError(f"Staging sign-in failed with HTTP {response.status_code}")
            payload = response.json()
            token = payload.get("access_token")
            user_id = (payload.get("user") or {}).get("id")
            if not token or not user_id:
                raise RuntimeError("Staging sign-in returned no valid user identity")
            return token, user_id

        token_a, user_a = sign_in(tenant_a_email, tenant_a_password)
        token_b, user_b = sign_in(tenant_b_email, tenant_b_password)
        if user_a == user_b:
            print("FAIL: tenant A and tenant B must be different test users.", file=sys.stderr)
            return 2

        def api_get(path: str, token: str) -> httpx.Response:
            return client.get(f"{api_base}{path}", headers={"Authorization": f"Bearer {token}"})

        orgs_a = api_get("/v1/organizations", token_a)
        orgs_b = api_get("/v1/organizations", token_b)
        if orgs_a.status_code != 200 or orgs_b.status_code != 200:
            print(
                f"FAIL: organization listing returned A={orgs_a.status_code}, B={orgs_b.status_code}.",
                file=sys.stderr,
            )
            return 1
        if not any(row.get("id") == organization_id for row in orgs_a.json().get("items", [])):
            print("FAIL: tenant A cannot see its pre-provisioned staging organization.", file=sys.stderr)
            return 1
        if any(row.get("id") == organization_id for row in orgs_b.json().get("items", [])):
            print("FAIL: tenant B can see tenant A's organization.", file=sys.stderr)
            return 1

        members_a = api_get(f"/v1/organizations/{organization_id}/memberships", token_a)
        members_b = api_get(f"/v1/organizations/{organization_id}/memberships", token_b)
        if members_a.status_code != 200 or not any(
            row.get("user_id") == user_a and row.get("role") == "owner"
            for row in members_a.json().get("items", [])
        ):
            print("FAIL: tenant A cannot verify its owner membership.", file=sys.stderr)
            return 1
        if members_b.status_code != 404:
            print(
                f"FAIL: cross-tenant membership lookup returned HTTP {members_b.status_code}, expected 404.",
                file=sys.stderr,
            )
            return 1

        headers_a = {"apikey": publishable_key, "Authorization": f"Bearer {token_a}"}
        headers_b = {"apikey": publishable_key, "Authorization": f"Bearer {token_b}"}
        audit_a = client.get(
            f"{supabase_url}/rest/v1/audit_events",
            headers=headers_a,
            params={"select": "id,organization_id,action", "organization_id": f"eq.{organization_id}", "limit": "5"},
        )
        audit_b = client.get(
            f"{supabase_url}/rest/v1/audit_events",
            headers=headers_b,
            params={"select": "id,organization_id,action", "organization_id": f"eq.{organization_id}", "limit": "5"},
        )
        if audit_a.status_code != 200 or audit_b.status_code != 200:
            print(
                f"FAIL: audit read returned A={audit_a.status_code}, B={audit_b.status_code}.",
                file=sys.stderr,
            )
            return 1
        if not audit_a.json():
            print("FAIL: tenant owner cannot read the pre-provisioned tenant audit evidence.", file=sys.stderr)
            return 1
        if audit_b.json():
            print("FAIL: tenant B can read tenant A's audit events.", file=sys.stderr)
            return 1

        # Both requests must be denied by database grants/RLS. These are intentional
        # negative probes and do not mutate data if the policies are correct.
        membership_escalation = client.post(
            f"{supabase_url}/rest/v1/organization_memberships",
            headers={**headers_b, "Content-Type": "application/json", "Prefer": "return=minimal"},
            json={"organization_id": organization_id, "user_id": user_b, "role": "admin"},
        )
        if membership_escalation.status_code < 400:
            print("FAIL: tenant B could self-assign an organization admin membership.", file=sys.stderr)
            return 1

        ownership_escalation = client.patch(
            f"{supabase_url}/rest/v1/organizations",
            headers={**headers_a, "Content-Type": "application/json", "Prefer": "return=representation"},
            params={"id": f"eq.{organization_id}"},
            json={"owner_id": user_b},
        )
        if ownership_escalation.status_code < 400:
            print("FAIL: tenant A could change the server-owned organization owner_id directly.", file=sys.stderr)
            return 1

        protected_profile_update = client.patch(
            f"{supabase_url}/rest/v1/profiles",
            headers={**headers_b, "Content-Type": "application/json", "Prefer": "return=representation"},
            params={"id": f"eq.{user_a}"},
            json={"account_status": "deactivation_requested"},
        )
        if protected_profile_update.status_code < 400:
            print("FAIL: tenant B could update another user's server-owned account_status.", file=sys.stderr)
            return 1

    print(
        "PASS: cross-tenant organization/membership/audit isolation; "
        "membership escalation, owner_id escalation, and cross-user profile mutation denied."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        # Never print request headers, tokens, passwords, or response bodies.
        print(f"FAIL: staging tenant-isolation check could not complete: {exc}", file=sys.stderr)
        raise SystemExit(1)
