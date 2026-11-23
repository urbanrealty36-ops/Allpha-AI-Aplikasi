"""Supabase Auth and user-scoped PostgREST access for ENG-P02."""
from __future__ import annotations

import os
from typing import Any

import httpx
import jwt
import uuid
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


async def current_session_user(
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
    # Only an explicit Auth rejection proves that the presented token is invalid.
    # Rate limits, gateway errors and unexpected upstream responses must not make
    # clients discard a potentially valid local session.
    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail={"code": "AUTH_UNAVAILABLE", "message": "Layanan autentikasi sementara tidak dapat memverifikasi sesi."},
        )
    user = response.json()
    if not user.get("id"):
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Token tidak memiliki identitas pengguna."})

    # Supabase Auth validates signature/expiry above. The session_id claim is read
    # only after that remote validation, then fenced against auth.sessions using
    # an auth.uid()-scoped RPC so a revoked refresh session cannot keep using an
    # otherwise-unexpired access JWT for protected API operations.
    try:
        claims = jwt.decode(
            credentials.credentials,
            options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
        )
        # The remote Auth response is authoritative. Bind the locally-read
        # session claims to that same identity before using any claim for access.
        if str(claims.get("sub") or "") != str(user["id"]):
            raise HTTPException(
                status_code=401,
                detail={"code": "IDENTITY_MISMATCH", "message": "Identitas token tidak cocok dengan sesi autentikasi."},
            )
        session_id = uuid.UUID(str(claims.get("session_id") or claims.get("sid") or ""))
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail={"code": "SESSION_INVALID", "message": "Sesi tidak memiliki identitas yang valid."})

    active = await user_db_request(
        "POST", "rpc/is_auth_session_active", credentials.credentials,
        body={"p_session_id": str(session_id)},
    )
    if active is not True:
        raise HTTPException(status_code=401, detail={"code": "SESSION_REVOKED", "message": "Sesi telah dicabut atau kedaluwarsa. Silakan masuk kembali."})

    request.state.user_id = user["id"]
    request.state.auth_session_id = str(session_id)
    request.state.supabase_access_token = credentials.credentials
    return user


async def current_user(
    request: Request,
    user: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    # Account lifecycle is a server-side authorization boundary, not a UI hint.
    # A deactivation request immediately prevents further protected API use,
    # even when the caller still holds an otherwise-valid Supabase access JWT.
    profile = await user_db_request(
        "GET",
        "profiles",
        request.state.supabase_access_token,
        params={
            "select": "id,account_status",
            "id": f"eq.{user['id']}",
            "limit": "1",
        },
    )
    if not profile:
        raise HTTPException(
            status_code=403,
            detail={"code": "ACCOUNT_PROFILE_UNAVAILABLE", "message": "Profil akun tidak tersedia; akses ditolak."},
        )
    if profile[0].get("account_status") != "active":
        raise HTTPException(
            status_code=403,
            detail={"code": "ACCOUNT_NOT_ACTIVE", "message": "Akun sedang dinonaktifkan dan tidak dapat menggunakan layanan."},
        )


    return user



async def optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    """Resolve an optional session for public-read endpoints; never grants write access."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    # Reuse the same remote Supabase Auth and session fence, then apply account state.
    session_user = await current_session_user(request, credentials)
    return await current_user(request, session_user)


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
    if response.status_code == 404:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        # PostgREST uses schema-cache errors for missing tables, columns and
        # RPC signatures. Treat these as dependency/schema drift, not a
        # resource-level 404 that could be mistaken for a tenant denial.
        if isinstance(payload, dict) and payload.get("code") in ("PGRST202", "PGRST203", "PGRST204", "PGRST205"):
            raise HTTPException(
                status_code=503,
                detail={"code": "DATABASE_SCHEMA_UNAVAILABLE", "message": "Kontrak layanan database belum tersedia. Coba lagi setelah sinkronisasi skema."},
            )
    if response.status_code >= 500:
        raise HTTPException(status_code=503, detail={"code": "DATABASE_UNAVAILABLE", "message": "Database sementara tidak dapat diakses."})
    if response.status_code >= 400:
        # Avoid forwarding Postgres internals or SQL detail to the client.
        code = "VALIDATION_ERROR" if response.status_code in (400, 422) else "REQUEST_FAILED"
        raise HTTPException(status_code=response.status_code, detail={"code": code, "message": "Permintaan data tidak dapat diproses."})
    if not response.content:
        return None
    return response.json()


async def require_organization_membership(
    request: Request,
    organization_id: str,
    actor_user_id: str,
    *,
    allowed_roles: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """Resolve tenant membership from the caller's verified JWT, never client-supplied role data.

    Mutating RPCs repeat role checks transactionally; this API guard provides a
    fail-closed boundary before service-role execution and avoids revealing
    whether an organization exists to a non-member.
    """
    access_token = getattr(request.state, "supabase_access_token", None)
    trusted_actor_id = getattr(request.state, "user_id", None)
    if not trusted_actor_id or str(trusted_actor_id) != str(actor_user_id):
        raise HTTPException(
            status_code=401,
            detail={"code": "IDENTITY_MISMATCH", "message": "Identitas actor tidak cocok dengan sesi terverifikasi."},
        )
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_CONTEXT_MISSING", "message": "Konteks sesi terverifikasi tidak tersedia."},
        )
    rows = await user_db_request(
        "GET",
        "organization_memberships",
        access_token,
        params={
            "select": "organization_id,user_id,role",
            "organization_id": f"eq.{organization_id}",
            "user_id": f"eq.{actor_user_id}",
            "limit": "1",
        },
    )
    # PostgREST filters are expected to be exact, but authorization must not
    # trust a response row solely because the query asked for this tenant.
    # Re-bind both tenant and actor identities before accepting the role.
    matching_rows = [
        row for row in rows
        if str(row.get("organization_id") or "") == str(organization_id)
        and str(row.get("user_id") or "") == str(actor_user_id)
    ]
    if len(matching_rows) != 1:
        raise HTTPException(
            status_code=404,
            detail={"code": "ORGANIZATION_NOT_FOUND", "message": "Organisasi tidak ditemukan."},
        )
    membership = matching_rows[0]
    role = membership.get("role")
    if allowed_roles is not None and role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail={"code": "ORGANIZATION_FORBIDDEN", "message": "Hak akses organisasi tidak mencukupi."},
        )
    return membership


async def service_db_request(function_name: str, *, body: dict[str, Any]) -> Any:
    """Invoke a server-only Supabase RPC using the backend service-role secret."""
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not service_key:
        raise HTTPException(status_code=503, detail={"code": "SERVICE_DATABASE_NOT_CONFIGURED", "message": "Layanan data server belum dikonfigurasi."})
    if not function_name.isidentifier():
        raise HTTPException(status_code=500, detail={"code": "SERVICE_RPC_INVALID", "message": "Kontrak RPC internal tidak valid."})
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(f"{url}/rest/v1/rpc/{function_name}", headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail={"code": "SERVICE_DATABASE_UNAVAILABLE", "message": "Layanan data server sementara tidak tersedia."}) from exc
    if response.status_code >= 500:
        raise HTTPException(status_code=503, detail={"code": "SERVICE_DATABASE_UNAVAILABLE", "message": "Layanan data server sementara tidak tersedia."})
    if response.status_code >= 400:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        sqlstate = payload.get("code") if isinstance(payload, dict) else None
        is_social_rpc = function_name.startswith(("create_social_edge_", "accept_social_follow_", "reject_social_follow_", "remove_social_edge_"))
        is_account_lifecycle_rpc = function_name.startswith(("create_account_deletion_request_for_actor",))
        is_consent_rpc = function_name.startswith(("record_account_consent_event_for_actor",))
        is_interest_rpc = function_name.startswith(("set_my_interest_preference_for_actor", "delete_my_interest_for_actor", "find_interest_discovery_candidates"))
        if sqlstate == "42501":
            if is_interest_rpc:
                raise HTTPException(status_code=403, detail={"code": "INTEREST_WRITE_FORBIDDEN", "message": "Perubahan minat tidak diizinkan."})
            if is_consent_rpc:
                raise HTTPException(status_code=403, detail={"code": "CONSENT_EVENT_FORBIDDEN", "message": "Perubahan persetujuan tidak diizinkan oleh kebijakan akun."})
            if is_social_rpc:
                raise HTTPException(status_code=403, detail={"code": "SOCIAL_EDGE_FORBIDDEN", "message": "Tindakan relasi sosial tidak diizinkan oleh kebijakan akun atau kepemilikan."})
            if is_account_lifecycle_rpc:
                raise HTTPException(status_code=409, detail={"code": "ACCOUNT_NOT_ACTIVE", "message": "Akun tidak berada pada status aktif untuk mengajukan penghapusan."})
            raise HTTPException(status_code=403, detail={"code": "ORGANIZATION_FORBIDDEN", "message": "Hak pengelolaan organisasi tidak tersedia."})
        if sqlstate in ("P0002", "23503"):
            if is_interest_rpc:
                raise HTTPException(status_code=404, detail={"code": "INTEREST_ACTOR_NOT_FOUND", "message": "Akun pemilik minat tidak ditemukan."})
            if is_consent_rpc:
                raise HTTPException(status_code=404, detail={"code": "CONSENT_ACTOR_NOT_FOUND", "message": "Akun pemilik persetujuan tidak ditemukan."})
            if is_social_rpc:
                raise HTTPException(status_code=404, detail={"code": "SOCIAL_TARGET_UNAVAILABLE", "message": "Identitas atau relasi sosial tidak tersedia."})
            if is_account_lifecycle_rpc:
                raise HTTPException(status_code=404, detail={"code": "ACCOUNT_NOT_FOUND", "message": "Akun tidak ditemukan."})
            raise HTTPException(status_code=404, detail={"code": "ORGANIZATION_MEMBER_NOT_FOUND", "message": "Anggota atau organisasi tidak ditemukan."})
        if sqlstate == "23505" or response.status_code == 409:
            if is_interest_rpc:
                raise HTTPException(status_code=409, detail={"code": "INTEREST_CONFLICT", "message": "Preferensi minat bertentangan dengan data yang tersimpan."})
            if is_consent_rpc:
                raise HTTPException(status_code=409, detail={"code": "CONSENT_IDEMPOTENCY_CONFLICT", "message": "Kunci idempotensi sudah digunakan untuk keputusan persetujuan yang berbeda."})
            if is_social_rpc:
                raise HTTPException(status_code=409, detail={"code": "SOCIAL_EDGE_CONFLICT", "message": "Relasi sosial sudah tercatat atau bertentangan."})
            if is_account_lifecycle_rpc:
                raise HTTPException(status_code=409, detail={"code": "ACCOUNT_DELETION_REQUEST_ALREADY_OPEN", "message": "Permintaan penghapusan akun yang belum selesai sudah ada."})
            raise HTTPException(status_code=409, detail={"code": "ORGANIZATION_MEMBER_CONFLICT", "message": "Keanggotaan organisasi sudah ada atau bertentangan."})
        if sqlstate == "22023" or response.status_code in (400, 422):
            if is_interest_rpc:
                raise HTTPException(status_code=422, detail={"code": "INTEREST_KEY_NOT_IN_CATALOG", "message": "Minat harus dipilih dari katalog resmi Allpha."})
            if is_consent_rpc:
                raise HTTPException(status_code=422, detail={"code": "CONSENT_EVENT_INPUT_INVALID", "message": "Data keputusan persetujuan tidak valid."})
            if is_social_rpc:
                raise HTTPException(status_code=422, detail={"code": "SOCIAL_EDGE_INPUT_INVALID", "message": "Data relasi sosial tidak valid."})
            raise HTTPException(status_code=422, detail={"code": "ORGANIZATION_INPUT_INVALID", "message": "Data organisasi atau keanggotaan tidak valid."})
        if response.status_code in (401, 403):
            raise HTTPException(status_code=503, detail={"code": "SERVICE_DATABASE_AUTH_INVALID", "message": "Kredensial layanan data server tidak valid."})
        raise HTTPException(status_code=503, detail={"code": "SERVICE_DATABASE_UNAVAILABLE", "message": "Layanan data server sementara tidak tersedia."})
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={"code": "SERVICE_DATABASE_RESPONSE_INVALID", "message": "Respons layanan data server tidak valid."}) from exc
