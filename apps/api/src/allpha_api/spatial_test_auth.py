"""Verify short-lived GitHub Actions OIDC tokens for trusted spatial ingestion jobs."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

REPOSITORY = "urbanrealty36-ops/Allpha-AI-Aplikasi"
REF = "refs/heads/main"
WORKFLOW_REF = f"{REPOSITORY}/.github/workflows/eng-p22-production-spatial-ingest.yml@{REF}"
ISSUER = "https://token.actions.githubusercontent.com"
AUDIENCE = "allpha-spatial-ingest"


@lru_cache(maxsize=1)
def _jwk_client() -> PyJWKClient:
    return PyJWKClient(f"{ISSUER}/.well-known/jwks", cache_jwk_set=True, lifespan=300)


def verify_spatial_ingest_oidc(token: str) -> dict[str, Any]:
    """Verify signature and constrain the token to the canonical production workflow."""
    signing_key = _jwk_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=AUDIENCE,
        issuer=ISSUER,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    if claims.get("repository") != REPOSITORY:
        raise jwt.InvalidTokenError("repository is not authorized")
    if claims.get("ref") != REF:
        raise jwt.InvalidTokenError("ref is not authorized")
    if claims.get("workflow_ref") != WORKFLOW_REF:
        raise jwt.InvalidTokenError("workflow is not authorized")
    if claims.get("event_name") not in {"push", "workflow_dispatch"}:
        raise jwt.InvalidTokenError("event is not authorized")
    return claims


def is_authorized_spatial_test_request(test_key: str | None, authorization: str | None) -> bool:
    """Accept either the dedicated server secret or the pinned GitHub OIDC workflow identity."""
    import os
    import secrets

    expected = os.getenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", "")
    if len(expected) >= 32 and test_key and secrets.compare_digest(test_key, expected):
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    token = authorization.removeprefix("Bearer ").strip()
    if not token or len(token) > 16384:
        return False
    try:
        verify_spatial_ingest_oidc(token)
        return True
    except Exception:
        return False
