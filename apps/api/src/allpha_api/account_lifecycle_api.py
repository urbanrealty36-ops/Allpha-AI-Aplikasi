"""Authenticated account export and deletion-request API (ENG-P03)."""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import quote
from typing import Any

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from typing import Literal

from allpha_api.auth import current_session_user, current_user, service_db_request, user_db_request

router = APIRouter(tags=["account-lifecycle"])
_SIGNED_EXPORT_URL_TTL_SECONDS = 900


class AccountDeletionRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: SecretStr = Field(min_length=1, max_length=256)
    confirmation_phrase: Literal["HAPUS AKUN ALLPHA SAYA"]


class AccountDeletionOwnershipTransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_type: Literal["agent", "organization"]
    resource_id: uuid.UUID
    successor_user_id: uuid.UUID


def _supabase_base() -> str:
    value = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    if not value:
        raise HTTPException(
            status_code=503,
            detail={"code": "SUPABASE_NOT_CONFIGURED", "message": "Layanan akun belum dikonfigurasi."},
        )
    return value


def _publishable_key() -> str:
    value = (os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip()
    if not value:
        raise HTTPException(
            status_code=503,
            detail={"code": "SUPABASE_NOT_CONFIGURED", "message": "Layanan akun belum dikonfigurasi."},
        )
    return value


def _valid_export_storage_path(user_id: str, job_id: uuid.UUID, storage_path: Any) -> bool:
    """Accept legacy and lease-scoped paths only within this user's export job."""
    if not isinstance(storage_path, str):
        return False
    legacy_path = f"{user_id}/{job_id}.json.gz"
    if storage_path == legacy_path:
        return True
    prefix = f"{user_id}/{job_id}/"
    if not storage_path.startswith(prefix) or not storage_path.endswith(".json.gz"):
        return False
    lease_token = storage_path[len(prefix):-len(".json.gz")]
    try:
        return str(uuid.UUID(lease_token)) == lease_token
    except (ValueError, TypeError, AttributeError):
        return False




def _export_artifact_expired(expires_at: Any) -> bool:
    if expires_at is None:
        return False
    if not isinstance(expires_at, str):
        return True
    try:
        value = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if value.tzinfo is None:
            return True
        return value <= datetime.now(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return True


def _service_key() -> str:
    value = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if not value:
        raise HTTPException(
            status_code=503,
            detail={"code": "ACCOUNT_EXPORT_STORAGE_UNAVAILABLE", "message": "Unduhan ekspor akun belum dikonfigurasi."},
        )
    return value


async def _verify_password_and_revoke_reauth_session(user: dict[str, Any], password: SecretStr) -> None:
    email = str(user.get("email") or "").strip()
    if not email:
        raise HTTPException(
            status_code=409,
            detail={"code": "ACCOUNT_EMAIL_REQUIRED", "message": "Email akun diperlukan untuk verifikasi ulang."},
        )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(
                f"{_supabase_base()}/auth/v1/token?grant_type=password",
                headers={"apikey": _publishable_key(), "Content-Type": "application/json"},
                json={"email": email, "password": password.get_secret_value()},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "REAUTHENTICATION_UNAVAILABLE", "message": "Verifikasi ulang akun sedang tidak tersedia."},
        ) from exc

    if response.status_code in (400, 401, 403):
        raise HTTPException(
            status_code=401,
            detail={"code": "REAUTHENTICATION_FAILED", "message": "Kata sandi tidak dapat diverifikasi."},
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail={"code": "REAUTHENTICATION_UNAVAILABLE", "message": "Verifikasi ulang akun sedang tidak tersedia."},
        )

    try:
        payload = response.json()
        reauth_user_id = str((payload.get("user") or {}).get("id") or "")
        access_token = str(payload.get("access_token") or "")
        claims = jwt.decode(
            access_token,
            options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
        )
        session_id = str(uuid.UUID(str(claims.get("session_id") or claims.get("sid") or "")))
        if reauth_user_id != str(user.get("id")) or str(claims.get("sub") or "") != str(user.get("id")):
            raise ValueError("reauthenticated identity mismatch")
    except (ValueError, TypeError, AttributeError, jwt.PyJWTError) as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "REAUTHENTICATION_SESSION_INVALID", "message": "Sesi verifikasi ulang tidak valid."},
        ) from exc

    # Password-grant reauthentication creates a new Auth session. Revoke that
    # short-lived session immediately; never persist its access/refresh tokens.
    try:
        revoked = await user_db_request(
            "POST",
            "rpc/revoke_my_auth_session",
            access_token,
            body={"p_session_id": session_id},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "REAUTHENTICATION_SESSION_CLEANUP_FAILED", "message": "Sesi verifikasi ulang belum dapat dibersihkan."},
        ) from exc
    if revoked is not True:
        raise HTTPException(
            status_code=503,
            detail={"code": "REAUTHENTICATION_SESSION_CLEANUP_FAILED", "message": "Sesi verifikasi ulang belum dapat dibersihkan."},
        )


@router.post("/v1/me/export-requests", status_code=202)
async def request_account_export(
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    idempotency_key = request.headers.get("Idempotency-Key", "").strip() or str(uuid.uuid4())
    if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_IDEMPOTENCY_KEY", "message": "Idempotency-Key harus 8–128 karakter alfanumerik atau . _ : -."},
        )
    rows = await user_db_request(
        "POST",
        "rpc/request_my_account_export",
        request.state.supabase_access_token,
        body={"p_idempotency_key": idempotency_key},
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(
            status_code=409,
            detail={"code": "ACCOUNT_EXPORT_NOT_QUEUED", "message": "Permintaan ekspor akun tidak dapat dimasukkan ke antrean."},
        )
    return {"export": rows[0], "idempotency_key": idempotency_key}


@router.get("/v1/me/export-requests")
async def list_account_exports(
    request: Request,
    user: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    rows = await user_db_request(
        "GET",
        "account_export_jobs",
        request.state.supabase_access_token,
        params={
            "select": "id,status,progress_percent,progress_stage,requested_at,started_at,completed_at,failed_at,expires_at,error_code,file_size_bytes,manifest",
            "user_id": f"eq.{user['id']}",
            "order": "requested_at.desc",
            "limit": "50",
        },
    )
    return {"items": rows if isinstance(rows, list) else []}


@router.get("/v1/me/export-requests/{job_id}/download")
async def get_account_export_download(
    job_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    rows = await user_db_request(
        "GET",
        "account_export_jobs",
        request.state.supabase_access_token,
        params={
            "select": "id,user_id,status,storage_bucket,storage_path,file_size_bytes,file_sha256,expires_at",
            "id": f"eq.{job_id}",
            "user_id": f"eq.{user['id']}",
            "limit": "1",
        },
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(
            status_code=404,
            detail={"code": "ACCOUNT_EXPORT_NOT_FOUND", "message": "Ekspor akun tidak ditemukan."},
        )
    job = rows[0]
    if job.get("status") == "expired" or _export_artifact_expired(job.get("expires_at")):
        raise HTTPException(
            status_code=410,
            detail={"code": "ACCOUNT_EXPORT_EXPIRED", "message": "Masa akses arsip ekspor telah berakhir."},
        )
    if job.get("status") != "succeeded":
        raise HTTPException(
            status_code=409,
            detail={"code": "ACCOUNT_EXPORT_NOT_READY", "message": "Ekspor akun belum siap diunduh."},
        )
    expected_path = job.get("storage_path")
    if job.get("storage_bucket") != "account-exports" or not _valid_export_storage_path(
        str(user["id"]), job_id, expected_path
    ):
        raise HTTPException(
            status_code=500,
            detail={"code": "ACCOUNT_EXPORT_STORAGE_SCOPE_INVALID", "message": "Lokasi berkas ekspor tidak valid."},
        )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(
                f"{_supabase_base()}/storage/v1/object/sign/account-exports/{quote(expected_path, safe='/')}",
                headers={
                    "apikey": _service_key(),
                    "Authorization": f"Bearer {_service_key()}",
                    "Content-Type": "application/json",
                },
                json={"expiresIn": _SIGNED_EXPORT_URL_TTL_SECONDS},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "ACCOUNT_EXPORT_STORAGE_UNAVAILABLE", "message": "Berkas ekspor belum dapat diakses."},
        ) from exc
    if response.status_code not in (200, 201):
        raise HTTPException(
            status_code=503,
            detail={"code": "ACCOUNT_EXPORT_STORAGE_UNAVAILABLE", "message": "Berkas ekspor belum dapat diakses."},
        )
    payload = response.json()
    signed_url = payload.get("signedURL") or payload.get("signedUrl")
    if not isinstance(signed_url, str) or not signed_url:
        raise HTTPException(
            status_code=503,
            detail={"code": "ACCOUNT_EXPORT_SIGNING_FAILED", "message": "Tautan unduhan belum dapat dibuat."},
        )
    if signed_url.startswith("/"):
        signed_url = _supabase_base() + signed_url
    return {
        "download_url": signed_url,
        "expires_in_seconds": _SIGNED_EXPORT_URL_TTL_SECONDS,
        "file_size_bytes": job.get("file_size_bytes"),
        "file_sha256": job.get("file_sha256"),
    }


@router.get("/v1/me/deletion-requests")
async def list_account_deletion_requests(
    request: Request,
    user: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    rows = await user_db_request(
        "GET",
        "account_deletion_requests",
        request.state.supabase_access_token,
        params={
            "select": "id,status,requested_at,policy_version,scheduled_for,completed_at,cancelled_at,updated_at",
            "user_id": f"eq.{user['id']}",
            "order": "requested_at.desc",
            "limit": "20",
        },
    )
    return {"items": rows if isinstance(rows, list) else []}


@router.post("/v1/me/deletion-requests", status_code=202)
async def request_account_deletion(
    payload: AccountDeletionRequestCreate,
    user: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    await _verify_password_and_revoke_reauth_session(user, payload.password)
    rows = await service_db_request(
        "create_account_deletion_request_for_actor",
        body={"p_actor_user_id": user["id"]},
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(
            status_code=409,
            detail={"code": "ACCOUNT_DELETION_NOT_RECORDED", "message": "Permintaan penghapusan akun tidak dapat dicatat."},
        )
    request_row = rows[0]
    execution_state = str(request_row.get("status") or "recorded")
    return {
        "deletion_request": request_row,
        "execution_state": execution_state,
        "message": (
            "Permintaan tercatat. Worker akan mengevaluasi retensi, legal hold, dan "
            "dependency; belum ada data yang dihapus sampai seluruh prasyarat "
            "eksekusi terpenuhi."
        ),
    }


@router.post("/v1/me/deletion-requests/{request_id}/ownership-transfers", status_code=202)
async def create_account_deletion_ownership_transfer(
    request_id: uuid.UUID,
    payload: AccountDeletionOwnershipTransferCreate,
    request: Request,
    user: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    transfer = await user_db_request(
        "POST",
        "rpc/set_my_account_deletion_ownership_transfer",
        request.state.supabase_access_token,
        body={
            "p_request_id": str(request_id),
            "p_resource_type": payload.resource_type,
            "p_resource_id": str(payload.resource_id),
            "p_successor_user_id": str(payload.successor_user_id),
        },
    )
    if not isinstance(transfer, dict) or transfer.get("status") != "requested":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ACCOUNT_DELETION_OWNERSHIP_TRANSFER_NOT_RECORDED",
                "message": "Pengalihan kepemilikan belum dapat dicatat.",
            },
        )
    return {"transfer": transfer, "execution": "pending_deletion_request"}


@router.post("/v1/me/deletion-requests/{request_id}/cancel")
async def cancel_account_deletion(
    request_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    cancelled = await user_db_request(
        "POST",
        "rpc/cancel_my_account_deletion",
        request.state.supabase_access_token,
        body={"p_request_id": str(request_id)},
    )
    if cancelled is not True:
        raise HTTPException(
            status_code=409,
            detail={"code": "ACCOUNT_DELETION_NOT_CANCELLABLE", "message": "Permintaan tidak ditemukan atau sudah melewati tahap pembatalan."},
        )
    return {"cancelled": True, "account_status": "active"}
