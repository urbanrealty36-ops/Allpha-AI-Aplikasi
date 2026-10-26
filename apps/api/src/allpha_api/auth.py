"""Supabase Auth and user-scoped PostgREST access for ENG-P02."""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)
_TIMEOUT = httpx.Timeout(8.0, connect=3.0)


def _config() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    if not url or not key:
        raise HTTPException(
            status_code=503,
            detail={"code": "SUPABASE_NOT_CONFIGURED", "message": "Supabase belum dikonfigurasi."},
        )
    return url, key


async def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Bearer token diperlukan."})
    url, key = _config()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{url}/auth/v1/user",
                headers={"apikey": key, "Authorization": f"Bearer {credentials.credentials}"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail={"code": "AUTH_UNAVAILABLE", "message": "Layanan autentikasi tidak tersedia."}) from exc
    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Sesi tidak valid atau telah berakhir."})
    if response.status_code >= 500:
        raise HTTPException(status_code=503, detail={"code": "AUTH_UNAVAILABLE", "message": "Layanan autentikasi tidak tersedia."})
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Sesi tidak valid."})
    user = response.json()
    if not user.get("id"):
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Token tidak memiliki identitas pengguna."})
    request.state.user_id = user["id"]
    request.state.supabase_access_token = credentials.credentials
    return user


async def optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    """Resolve an optional session for public-read endpoints; never grants write access."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    # Reuse the same remote Supabase Auth verification as protected routes.
    return await current_user(request, credentials)


async def user_db_request(
    method: str,
    path: str,
    access_token: str | None,
    *,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    prefer: str | None = None,
) -> Any:
    url, key = _config()
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
    }
    # Anonymous public reads send only the publishable API key so PostgREST uses the anon role.
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if prefer:
        headers["Prefer"] = prefer
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.request(
                method, f"{url}/rest/v1/{path}", headers=headers, params=params, json=body
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail={"code": "DATABASE_UNAVAILABLE", "message": "Database sementara tidak dapat diakses."}) from exc
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Sesi tidak valid atau telah berakhir."})
    if response.status_code == 403:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Akses ditolak oleh kebijakan otorisasi."})
    if response.status_code == 409:
        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Data bertentangan dengan data yang sudah ada."})
    if response.status_code >= 500:
        raise HTTPException(status_code=503, detail={"code": "DATABASE_UNAVAILABLE", "message": "Database sementara tidak dapat diakses."})
    if response.status_code >= 400:
        # Avoid forwarding Postgres internals or SQL detail to the client.
        code = "VALIDATION_ERROR" if response.status_code in (400, 422) else "REQUEST_FAILED"
        raise HTTPException(status_code=response.status_code, detail={"code": code, "message": "Permintaan data tidak dapat diproses."})
    if not response.content:
        return None
    return response.json()
