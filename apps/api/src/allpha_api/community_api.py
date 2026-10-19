"""ENG-P19 communities, collaboration workspaces and missions API."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user
from allpha_api.operator_security import require_operator_scope, write_operator_audit

router = APIRouter(prefix="/v1", tags=["communities-workspaces"])
TIMEOUT = httpx.Timeout(12, connect=3)


def _config() -> tuple[str, str]:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not base or not key:
        raise HTTPException(503, detail={"code": "COLLABORATION_NOT_CONFIGURED", "message": "Layanan komunitas belum dikonfigurasi."})
    return base, key


async def _db(method: str, table: str, *, params: dict[str, str] | None = None, body: Any = None, prefer: str | None = None) -> Any:
    base, key = _config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.request(method, f"{base}/rest/v1/{table}", params=params, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail={"code": "COLLABORATION_DATABASE_UNAVAILABLE", "message": "Data kolaborasi sementara tidak tersedia."}) from exc
    if response.status_code >= 400:
        detail = response.text.casefold()
        if response.status_code == 409 or "duplicate key" in detail or "unique constraint" in detail or "idempotency_conflict" in detail:
            raise HTTPException(409, detail={"code": "COLLABORATION_CONFLICT", "message": "Data berubah atau permintaan duplikat. Muat ulang lalu coba lagi."})
        if "mission_not_started" in detail:
            raise HTTPException(409, detail={"code": "MISSION_NOT_STARTED", "message": "Misi belum dimulai."})
        if "mission_ended" in detail:
            raise HTTPException(409, detail={"code": "MISSION_ENDED", "message": "Misi telah berakhir."})
        if "mission_not_found_or_inactive" in detail:
            raise HTTPException(404, detail={"code": "MISSION_NOT_FOUND", "message": "Misi tidak ditemukan atau tidak aktif."})
        if "membership_required" in detail or response.status_code in (401, 403):
            raise HTTPException(403, detail={"code": "COLLABORATION_FORBIDDEN", "message": "Operasi tidak diizinkan."})
        if "community_not_joinable" in detail:
            raise HTTPException(404, detail={"code": "COMMUNITY_NOT_JOINABLE", "message": "Komunitas ini tidak dapat diikuti secara publik."})
        raise HTTPException(503, detail={"code": "COLLABORATION_DATABASE_ERROR", "message": "Data kolaborasi tidak dapat diproses."})
    return response.json() if response.content else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _community(community_id: uuid.UUID) -> dict[str, Any]:
    rows = await _db("GET", "communities", params={"select": "*", "id": f"eq.{community_id}", "status": "eq.active", "limit": "1"})
    if not rows:
        raise HTTPException(404, detail={"code": "COMMUNITY_NOT_FOUND", "message": "Komunitas tidak ditemukan atau tidak aktif."})
    return rows[0]

async def _membership(community_id: uuid.UUID, user_id: str) -> dict[str, Any] | None:
    rows = await _db("GET", "community_memberships", params={"select": "*", "community_id": f"eq.{community_id}", "user_id": f"eq.{user_id}", "status": "eq.active", "limit": "1"})
    return rows[0] if rows else None


async def _require_member(community_id: uuid.UUID, user_id: str, roles: tuple[str, ...] = ("owner", "moderator", "member")) -> dict[str, Any]:
    membership = await _membership(community_id, user_id)
    if not membership or membership.get("role") not in roles:
        raise HTTPException(403, detail={"code": "COMMUNITY_MEMBERSHIP_REQUIRED", "message": "Akses komunitas memerlukan keanggotaan yang aktif."})
    return membership


async def _workspace(workspace_id: uuid.UUID) -> dict[str, Any]:
    rows = await _db("GET", "workspaces", params={"select": "*", "id": f"eq.{workspace_id}", "status": "eq.active", "limit": "1"})
    if not rows:
        raise HTTPException(404, detail={"code": "WORKSPACE_NOT_FOUND", "message": "Workspace tidak ditemukan."})
    return rows[0]


async def _require_workspace(workspace_id: uuid.UUID, user_id: str, write: bool = False) -> dict[str, Any]:
    workspace = await _workspace(workspace_id)
    rows = await _db("GET", "workspace_memberships", params={"select": "*", "workspace_id": f"eq.{workspace_id}", "user_id": f"eq.{user_id}", "status": "eq.active", "limit": "1"})
    if not rows:
        raise HTTPException(403, detail={"code": "WORKSPACE_ACCESS_DENIED", "message": "Anda bukan anggota workspace ini."})
    membership = rows[0]
    if write and membership.get("role") not in ("owner", "editor"):
        raise HTTPException(403, detail={"code": "WORKSPACE_READ_ONLY", "message": "Peran Anda hanya dapat membaca workspace."})
    return {"workspace": workspace, "membership": membership}


class CommunityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80)
    slug: str = Field(min_length=3, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$")
    description: str = Field(default="", max_length=1000)
    visibility: Literal["public", "private"] = "public"


class CommunityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    visibility: Literal["public", "private"] | None = None


class CommunityPostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=5000)
    post_type: Literal["discussion", "announcement", "resource", "event"] = "discussion"


class CommunityPostPinUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pinned: bool


class CommunityPostModerationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["published", "hidden", "removed"]
    reason: str = Field(min_length=8, max_length=500)


class InviteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["member", "moderator"] = "member"
    expires_in_hours: int = Field(default=168, ge=1, le=720)


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["moderator", "member"]


class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    community_id: uuid.UUID | None = None
    visibility: Literal["private", "community"] = "private"


class WorkspaceDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(default="", max_length=50000)


class WorkspaceDocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(default="", max_length=50000)
    expected_version: int = Field(ge=1)


class AnnotationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: uuid.UUID
    body: str = Field(min_length=1, max_length=4000)
    anchor: dict[str, Any] = Field(default_factory=dict)


class MissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    target_count: int = Field(default=1, ge=1, le=100000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


@router.get("/communities")
async def list_communities(q: str | None = Query(default=None, max_length=80), limit: int = Query(default=30, ge=1, le=100), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    user_id = str(user["id"])
    public = await _db("GET", "communities", params={"select": "*", "visibility": "eq.public", "status": "eq.active", "order": "updated_at.desc", "limit": str(limit)})
    own_memberships = await _db("GET", "community_memberships", params={"select": "community_id,role,status", "user_id": f"eq.{user_id}", "status": "eq.active", "limit": "500"})
    own_ids = {m["community_id"] for m in (own_memberships or [])}
    private = []
    if own_ids:
        private = await _db("GET", "communities", params={"select": "*", "id": "in.(" + ",".join(own_ids) + ")", "status": "eq.active", "limit": str(limit)})
    by_id = {row["id"]: row for row in [*(public or []), *(private or [])]}
    items = list(by_id.values())
    if q:
        needle = q.casefold()
        items = [x for x in items if needle in x["name"].casefold() or needle in (x.get("description") or "").casefold()]
    for item in items:
        item["membership_role"] = next((m["role"] for m in (own_memberships or []) if m["community_id"] == item["id"]), None)
    return {"items": items[:limit]}


@router.post("/communities", status_code=201)
async def create_community(payload: CommunityCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _db("POST", "rpc/create_community_with_owner", body={"p_name": payload.name.strip(), "p_slug": payload.slug, "p_description": payload.description.strip(), "p_visibility": payload.visibility, "p_created_by": str(user["id"])}, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "COMMUNITY_CREATE_FAILED", "message": "Komunitas tidak dapat dibuat."})
    return {"community": rows[0], "membership_role": "owner"}

@router.get("/communities/{community_id}")
async def get_community(community_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    row = await _community(community_id)
    membership = await _membership(community_id, str(user["id"]))
    if row["visibility"] == "private" and not membership:
        raise HTTPException(404, detail={"code": "COMMUNITY_NOT_FOUND", "message": "Komunitas tidak ditemukan."})
    return {"community": row, "membership": membership}


@router.patch("/communities/{community_id}")
async def update_community(community_id: uuid.UUID, payload: CommunityUpdate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    membership = await _require_member(community_id, str(user["id"]), ("owner",))
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(422, detail={"code": "EMPTY_UPDATE", "message": "Tidak ada perubahan yang dikirim."})
    changes["updated_at"] = _now()
    rows = await _db("PATCH", "communities", params={"id": f"eq.{community_id}", "created_by": f"eq.{user['id']}"}, body=changes, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "COMMUNITY_UPDATE_CONFLICT", "message": "Komunitas tidak dapat diperbarui."})
    return {"community": rows[0]}


@router.post("/communities/{community_id}/join", status_code=201)
async def join_community(community_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    community = await _community(community_id)
    if community["visibility"] != "public":
        raise HTTPException(404, detail={"code": "COMMUNITY_NOT_JOINABLE", "message": "Komunitas ini tidak dapat diikuti secara publik."})
    rows = await _db("POST", "rpc/join_public_community", body={"p_community_id": str(community_id), "p_user_id": str(user["id"])}, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "COMMUNITY_JOIN_FAILED", "message": "Keanggotaan tidak dapat disimpan."})
    return {"membership": rows[0]}

@router.get("/communities/{community_id}/members")
async def list_members(community_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_member(community_id, str(user["id"]))
    rows = await _db("GET", "community_memberships", params={"select": "community_id,user_id,role,status,joined_at", "community_id": f"eq.{community_id}", "status": "eq.active", "order": "joined_at.asc", "limit": "500"})
    return {"items": rows or []}


@router.patch("/communities/{community_id}/members/{member_id}")
async def update_member_role(community_id: uuid.UUID, member_id: uuid.UUID, payload: RoleUpdate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_member(community_id, str(user["id"]), ("owner",))
    if str(member_id) == str(user["id"]):
        raise HTTPException(409, detail={"code": "OWNER_ROLE_IMMUTABLE", "message": "Pemilik tidak dapat mengubah perannya sendiri."})
    rows = await _db("PATCH", "community_memberships", params={"community_id": f"eq.{community_id}", "user_id": f"eq.{member_id}", "status": "eq.active", "role": "neq.owner"}, body={"role": payload.role, "updated_at": _now()}, prefer="return=representation")
    if not rows:
        raise HTTPException(404, detail={"code": "MEMBER_NOT_FOUND", "message": "Anggota tidak ditemukan."})
    return {"membership": rows[0]}


@router.delete("/communities/{community_id}/members/{member_id}", status_code=204)
async def remove_member(community_id: uuid.UUID, member_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> None:
    actor_id = str(user["id"])
    target_id = str(member_id)
    actor = await _require_member(community_id, actor_id)
    target = await _membership(community_id, target_id)
    if not target:
        raise HTTPException(404, detail={"code": "MEMBER_NOT_FOUND", "message": "Anggota tidak ditemukan."})
    if target.get("role") == "owner":
        raise HTTPException(409, detail={"code": "OWNER_CANNOT_BE_REMOVED", "message": "Pemilik komunitas tidak dapat dikeluarkan."})
    if actor_id != target_id and actor.get("role") not in ("owner", "moderator"):
        raise HTTPException(403, detail={"code": "MEMBER_MANAGEMENT_DENIED", "message": "Hanya pemilik/moderator yang dapat mengelola anggota lain."})
    await _db("PATCH", "community_memberships", params={"community_id": f"eq.{community_id}", "user_id": f"eq.{target_id}", "status": "eq.active"}, body={"status": "removed", "updated_at": _now()}, prefer="return=minimal")


@router.post("/communities/{community_id}/invites", status_code=201)
async def create_invite(community_id: uuid.UUID, payload: InviteCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_member(community_id, str(user["id"]), ("owner", "moderator"))
    token = str(uuid.uuid4())
    from datetime import timedelta
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)).isoformat()
    rows = await _db("POST", "community_invites", body={"community_id": str(community_id), "created_by": str(user["id"]), "token_hash": __import__("hashlib").sha256(token.encode()).hexdigest(), "role": payload.role, "expires_at": expires_at}, prefer="return=representation")
    return {"invite": {"id": rows[0]["id"], "token": token, "expires_at": expires_at, "role": payload.role}}


@router.post("/community-invites/{token}/accept", status_code=201)
async def accept_invite(token: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    import hashlib
    digest = hashlib.sha256(token.encode()).hexdigest()
    rows = await _db("GET", "community_invites", params={"select": "*", "token_hash": f"eq.{digest}", "accepted_at": "is.null", "revoked_at": "is.null", "expires_at": f"gt.{_now()}", "limit": "1"})
    if not rows:
        raise HTTPException(404, detail={"code": "INVITE_INVALID", "message": "Undangan tidak valid atau telah kedaluwarsa."})
    invite = rows[0]
    community_id = uuid.UUID(invite["community_id"])
    current = await _membership(community_id, str(user["id"]))
    if current:
        return {"membership": current, "already_member": True}
    memberships = await _db("POST", "community_memberships", body={"community_id": str(community_id), "user_id": str(user["id"]), "role": invite["role"], "status": "active", "joined_at": _now()}, prefer="return=representation")
    await _db("PATCH", "community_invites", params={"id": f"eq.{invite['id']}", "accepted_at": "is.null"}, body={"accepted_at": _now(), "accepted_by": str(user["id"])}, prefer="return=minimal")
    return {"membership": memberships[0]}


@router.get("/communities/{community_id}/posts")
async def list_community_posts(community_id: uuid.UUID, limit: int = Query(default=30, ge=1, le=100), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    community = await _community(community_id)
    if community["visibility"] == "private":
        await _require_member(community_id, str(user["id"]))
    rows = await _db("GET", "community_posts", params={"select": "*", "community_id": f"eq.{community_id}", "status": "eq.published", "order": "is_pinned.desc,pinned_at.desc,created_at.desc", "limit": str(limit)})
    return {"items": rows or []}


@router.delete("/communities/{community_id}/invites/{invite_id}", status_code=204)
async def revoke_invite(community_id: uuid.UUID, invite_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> None:
    await _require_member(community_id, str(user["id"]), ("owner", "moderator"))
    rows = await _db("PATCH", "community_invites", params={"id": f"eq.{invite_id}", "community_id": f"eq.{community_id}", "accepted_at": "is.null", "revoked_at": "is.null"}, body={"revoked_at": _now()}, prefer="return=representation")
    if not rows:
        raise HTTPException(404, detail={"code": "INVITE_NOT_FOUND", "message": "Undangan tidak ditemukan atau sudah digunakan."})
@router.post("/communities/{community_id}/posts", status_code=201)
async def create_community_post(community_id: uuid.UUID, payload: CommunityPostCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _community(community_id)
    await _require_member(community_id, str(user["id"]))
    rows = await _db("POST", "community_posts", body={"community_id": str(community_id), "author_id": str(user["id"]), "body": payload.body.strip(), "post_type": payload.post_type, "status": "published"}, prefer="return=representation")
    return {"post": rows[0]}


@router.patch("/communities/{community_id}/posts/{post_id}/pin")
async def update_community_post_pin(community_id: uuid.UUID, post_id: uuid.UUID, payload: CommunityPostPinUpdate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _community(community_id)
    await _require_member(community_id, str(user["id"]), ("owner", "moderator"))
    rows = await _db("PATCH", "community_posts", params={"id": f"eq.{post_id}", "community_id": f"eq.{community_id}", "status": "eq.published", "post_type": "eq.resource"}, body={"is_pinned": payload.pinned, "pinned_by": str(user["id"]) if payload.pinned else None, "pinned_at": _now() if payload.pinned else None, "updated_at": _now()}, prefer="return=representation")
    if not rows:
        raise HTTPException(404, detail={"code": "COMMUNITY_POST_NOT_FOUND", "message": "Sumber daya tidak ditemukan atau tidak berstatus published."})
    return {"post": rows[0]}


@router.patch("/communities/{community_id}/posts/{post_id}/moderation")
async def moderate_community_post(community_id: uuid.UUID, post_id: uuid.UUID, payload: CommunityPostModerationUpdate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _community(community_id)
    await _require_member(community_id, str(user["id"]), ("owner", "moderator"))
    rows = await _db("GET", "community_posts", params={"select": "id,community_id,status,author_id", "id": f"eq.{post_id}", "community_id": f"eq.{community_id}", "limit": "1"})
    if not rows:
        raise HTTPException(404, detail={"code": "COMMUNITY_POST_NOT_FOUND", "message": "Konten komunitas tidak ditemukan."})
    await write_operator_audit(request, actor_user_id=str(user["id"]), action="community.post.moderate", outcome="attempted", resource_type="community_post", resource_id=str(post_id), metadata={"community_id": str(community_id), "status": payload.status, "reason": payload.reason})
    changed = await _db("PATCH", "community_posts", params={"id": f"eq.{post_id}", "community_id": f"eq.{community_id}"}, body={"status": payload.status, "is_pinned": False if payload.status != "published" else None, "pinned_by": None if payload.status != "published" else None, "pinned_at": None if payload.status != "published" else None, "updated_at": _now()}, prefer="return=representation")
    if not changed:
        raise HTTPException(409, detail={"code": "COMMUNITY_POST_MODERATION_CONFLICT", "message": "Status konten berubah; muat ulang dan coba lagi."})
    return {"post": changed[0], "reason": payload.reason}


@router.post("/communities/{community_id}/reports", status_code=201)
async def report_community(community_id: uuid.UUID, reason: str = Query(min_length=8, max_length=500), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _community(community_id)
    rows = await _db("POST", "community_reports", body={"community_id": str(community_id), "reporter_id": str(user["id"]), "reason": reason.strip(), "status": "open"}, prefer="return=representation")
    return {"report": {"id": rows[0]["id"], "status": rows[0]["status"]}}


@router.get("/workspaces")
async def list_workspaces(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    memberships = await _db("GET", "workspace_memberships", params={"select": "workspace_id,role", "user_id": f"eq.{user['id']}", "status": "eq.active", "limit": "500"})
    ids = [m["workspace_id"] for m in (memberships or [])]
    if not ids:
        return {"items": []}
    rows = await _db("GET", "workspaces", params={"select": "*", "id": "in.(" + ",".join(ids) + ")", "status": "eq.active", "order": "updated_at.desc", "limit": "100"})
    roles = {m["workspace_id"]: m["role"] for m in memberships}
    for row in rows or []:
        row["membership_role"] = roles.get(row["id"])
    return {"items": rows or []}


@router.post("/workspaces", status_code=201)
async def create_workspace(payload: WorkspaceCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    user_id = str(user["id"])
    if payload.visibility == "community" and not payload.community_id:
        raise HTTPException(422, detail={"code": "COMMUNITY_REQUIRED", "message": "Workspace komunitas harus terikat pada komunitas."})
    if payload.community_id:
        await _require_member(payload.community_id, user_id)
    rows = await _db("POST", "rpc/create_workspace_with_owner", body={"p_title": payload.title.strip(), "p_description": payload.description.strip(), "p_created_by": user_id, "p_community_id": str(payload.community_id) if payload.community_id else None, "p_visibility": payload.visibility}, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "WORKSPACE_CREATE_FAILED", "message": "Workspace tidak dapat dibuat."})
    return {"workspace": rows[0]}

@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    access = await _require_workspace(workspace_id, str(user["id"]))
    return {"workspace": access["workspace"], "membership": access["membership"]}


@router.post("/workspaces/{workspace_id}/members", status_code=201)
async def add_workspace_member(workspace_id: uuid.UUID, member_id: uuid.UUID, role: Literal["editor", "viewer"] = "editor", user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    access = await _require_workspace(workspace_id, str(user["id"]), write=True)
    if access["membership"]["role"] != "owner":
        raise HTTPException(403, detail={"code": "WORKSPACE_OWNER_REQUIRED", "message": "Hanya pemilik workspace yang dapat menambahkan anggota."})
    rows = await _db("POST", "workspace_memberships", params={"on_conflict": "workspace_id,user_id"}, body={"workspace_id": str(workspace_id), "user_id": str(member_id), "role": role, "status": "active"}, prefer="resolution=merge-duplicates,return=representation")
    return {"membership": rows[0]}


@router.get("/workspaces/{workspace_id}/documents")
async def list_workspace_documents(workspace_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_workspace(workspace_id, str(user["id"]))
    rows = await _db("GET", "workspace_documents", params={"select": "id,workspace_id,title,version,updated_by,updated_at,created_at", "workspace_id": f"eq.{workspace_id}", "status": "eq.active", "order": "updated_at.desc", "limit": "200"})
    return {"items": rows or []}


@router.post("/workspaces/{workspace_id}/documents", status_code=201)
async def create_workspace_document(workspace_id: uuid.UUID, payload: WorkspaceDocumentCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_workspace(workspace_id, str(user["id"]), write=True)
    rows = await _db("POST", "workspace_documents", body={"workspace_id": str(workspace_id), "title": payload.title.strip(), "body": payload.body, "version": 1, "created_by": str(user["id"]), "updated_by": str(user["id"])}, prefer="return=representation")
    doc = rows[0]
    await _db("POST", "workspace_document_versions", body={"document_id": doc["id"], "version": 1, "title": doc["title"], "body": doc["body"], "created_by": str(user["id"])}, prefer="return=minimal")
    return {"document": doc}


@router.get("/workspaces/{workspace_id}/documents/{document_id}")
async def get_workspace_document(workspace_id: uuid.UUID, document_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_workspace(workspace_id, str(user["id"]))
    rows = await _db("GET", "workspace_documents", params={"select": "*", "id": f"eq.{document_id}", "workspace_id": f"eq.{workspace_id}", "status": "eq.active", "limit": "1"})
    if not rows:
        raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND", "message": "Dokumen tidak ditemukan."})
    return {"document": rows[0]}


@router.put("/workspaces/{workspace_id}/documents/{document_id}")
async def update_workspace_document(workspace_id: uuid.UUID, document_id: uuid.UUID, payload: WorkspaceDocumentUpdate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_workspace(workspace_id, str(user["id"]), write=True)
    rows = await _db("GET", "workspace_documents", params={"select": "*", "id": f"eq.{document_id}", "workspace_id": f"eq.{workspace_id}", "status": "eq.active", "limit": "1"})
    if not rows:
        raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND", "message": "Dokumen tidak ditemukan."})
    current = rows[0]
    if int(current["version"]) != payload.expected_version:
        raise HTTPException(409, detail={"code": "DOCUMENT_VERSION_CONFLICT", "message": "Dokumen telah berubah. Muat versi terbaru sebelum menyimpan."})
    version = int(current["version"]) + 1
    updated = await _db("PATCH", "workspace_documents", params={"id": f"eq.{document_id}", "workspace_id": f"eq.{workspace_id}", "version": f"eq.{payload.expected_version}"}, body={"title": payload.title.strip(), "body": payload.body, "version": version, "updated_by": str(user["id"]), "updated_at": _now()}, prefer="return=representation")
    if not updated:
        raise HTTPException(409, detail={"code": "DOCUMENT_VERSION_CONFLICT", "message": "Dokumen berubah bersamaan dengan penyimpanan."})
    await _db("POST", "workspace_document_versions", body={"document_id": str(document_id), "version": version, "title": payload.title.strip(), "body": payload.body, "created_by": str(user["id"])}, prefer="return=minimal")
    return {"document": updated[0]}


@router.get("/workspaces/{workspace_id}/documents/{document_id}/versions")
async def list_document_versions(workspace_id: uuid.UUID, document_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_workspace(workspace_id, str(user["id"]))
    rows = await _db("GET", "workspace_document_versions", params={"select": "id,document_id,version,title,created_by,created_at", "document_id": f"eq.{document_id}", "order": "version.desc", "limit": "100"})
    return {"items": rows or []}


@router.post("/workspaces/{workspace_id}/annotations", status_code=201)
async def create_annotation(workspace_id: uuid.UUID, payload: AnnotationCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_workspace(workspace_id, str(user["id"]), write=True)
    doc = await _db("GET", "workspace_documents", params={"select": "id", "id": f"eq.{payload.document_id}", "workspace_id": f"eq.{workspace_id}", "status": "eq.active", "limit": "1"})
    if not doc:
        raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND", "message": "Dokumen tidak ditemukan."})
    rows = await _db("POST", "workspace_annotations", body={"workspace_id": str(workspace_id), "document_id": str(payload.document_id), "author_id": str(user["id"]), "body": payload.body.strip(), "anchor": payload.anchor}, prefer="return=representation")
    return {"annotation": rows[0]}


@router.get("/workspaces/{workspace_id}/annotations")
async def list_annotations(workspace_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_workspace(workspace_id, str(user["id"]))
    rows = await _db("GET", "workspace_annotations", params={"select": "*", "workspace_id": f"eq.{workspace_id}", "status": "eq.active", "order": "created_at.asc", "limit": "500"})
    return {"items": rows or []}


@router.post("/workspaces/{workspace_id}/presence")
async def update_presence(workspace_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_workspace(workspace_id, str(user["id"]))
    rows = await _db("POST", "workspace_presence", params={"on_conflict": "workspace_id,user_id"}, body={"workspace_id": str(workspace_id), "user_id": str(user["id"]), "last_seen_at": _now()}, prefer="resolution=merge-duplicates,return=representation")
    return {"presence": rows[0] if rows else {"workspace_id": str(workspace_id), "last_seen_at": _now()}}


@router.get("/workspaces/{workspace_id}/presence")
async def list_presence(workspace_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _require_workspace(workspace_id, str(user["id"]))
    from datetime import timedelta
    active_since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    rows = await _db("GET", "workspace_presence", params={"select": "workspace_id,user_id,last_seen_at", "workspace_id": f"eq.{workspace_id}", "last_seen_at": f"gt.{active_since}", "order": "last_seen_at.desc", "limit": "100"})
    return {"items": rows or []}


@router.get("/communities/{community_id}/missions")
async def list_missions(community_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _community(community_id)
    await _require_member(community_id, str(user["id"]))
    rows = await _db("GET", "community_missions", params={"select": "*", "community_id": f"eq.{community_id}", "status": "eq.active", "order": "created_at.desc", "limit": "100"})
    progress = await _db("GET", "community_mission_progress", params={"select": "mission_id,progress_count,status", "user_id": f"eq.{user['id']}", "limit": "500"})
    progress_by_id = {x["mission_id"]: x for x in (progress or [])}
    for row in rows or []:
        row["my_progress"] = progress_by_id.get(row["id"], {"progress_count": 0, "status": "not_started"})
    return {"items": rows or []}


@router.post("/communities/{community_id}/missions", status_code=201)
async def create_mission(community_id: uuid.UUID, payload: MissionCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _community(community_id)
    await _require_member(community_id, str(user["id"]), ("owner", "moderator"))
    if payload.starts_at and payload.ends_at and payload.ends_at <= payload.starts_at:
        raise HTTPException(422, detail={"code": "MISSION_DATE_RANGE_INVALID", "message": "Waktu berakhir harus setelah waktu mulai."})
    rows = await _db("POST", "community_missions", body={"community_id": str(community_id), "created_by": str(user["id"]), "title": payload.title.strip(), "description": payload.description.strip(), "target_count": payload.target_count, "starts_at": payload.starts_at.isoformat() if payload.starts_at else None, "ends_at": payload.ends_at.isoformat() if payload.ends_at else None, "status": "active"}, prefer="return=representation")
    return {"mission": rows[0]}


@router.post("/communities/{community_id}/missions/{mission_id}/progress")
async def update_mission_progress(community_id: uuid.UUID, mission_id: uuid.UUID, increment: int = Query(default=1, ge=1, le=100), idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _community(community_id)
    await _require_member(community_id, str(user["id"]))
    rows = await _db("POST", "rpc/record_community_mission_progress", body={"p_community_id": str(community_id), "p_mission_id": str(mission_id), "p_user_id": str(user["id"]), "p_increment": increment, "p_idempotency_key": str(idempotency_key)}, prefer="return=representation")
    if not rows:
        raise HTTPException(404, detail={"code": "MISSION_NOT_FOUND", "message": "Misi tidak ditemukan atau tidak aktif."})
    return {"progress": rows[0], "reward_status": "not_configured"}

class CommunityReportReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["dismiss", "suspend_community"] 
    reason: str = Field(min_length=8, max_length=500)


@router.get("/admin/community-reports", tags=["community-moderation"])
async def list_community_reports(user: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    rows = await _db("GET", "community_reports", params={"select": "*", "status": "in.(open,reviewing)", "order": "created_at.asc", "limit": "100"})
    reports = rows or []
    ids = list(dict.fromkeys(str(row["community_id"]) for row in reports))
    by_id: dict[str, Any] = {}
    if ids:
        communities = await _db("GET", "communities", params={"select": "id,name,slug,visibility,status,created_by", "id": "in.(" + ",".join(ids) + ")", "limit": str(len(ids))})
        by_id = {str(row["id"]): row for row in (communities or [])}
    return {"items": [{**row, "community": by_id.get(str(row["community_id"]))} for row in reports]}


@router.post("/admin/community-reports/{report_id}/review", tags=["community-moderation"])
async def review_community_report(report_id: uuid.UUID, payload: CommunityReportReview, request: Request,
    user: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    reports = await _db("GET", "community_reports", params={"select": "*", "id": f"eq.{report_id}", "status": "in.(open,reviewing)", "limit": "1"})
    if not reports:
        raise HTTPException(404, detail={"code": "COMMUNITY_REPORT_NOT_FOUND", "message": "Laporan tidak ditemukan atau sudah ditinjau."})
    report = reports[0]
    await write_operator_audit(request, actor_user_id=str(user["id"]), action="community.report.review", outcome="attempted",
        resource_type="community_report", resource_id=str(report_id), metadata={"decision": payload.decision, "reason": payload.reason, "community_id": str(report["community_id"])})
    if payload.decision == "suspend_community":
        changed = await _db("PATCH", "communities", params={"id": f"eq.{report['community_id']}", "status": "eq.active"},
            body={"status": "suspended", "updated_at": _now()}, prefer="return=representation")
        if not changed:
            raise HTTPException(409, detail={"code": "COMMUNITY_REVIEW_CONFLICT", "message": "Komunitas berubah atau sudah ditangguhkan."})
    reviewed = await _db("PATCH", "community_reports", params={"id": f"eq.{report_id}", "status": "in.(open,reviewing)"},
        body={"status": "dismissed" if payload.decision == "dismiss" else "resolved", "reviewer_id": str(user["id"]), "review_reason": payload.reason, "reviewed_at": _now()}, prefer="return=representation")
    if not reviewed:
        raise HTTPException(409, detail={"code": "COMMUNITY_REPORT_REVIEW_CONFLICT", "message": "Laporan ditinjau oleh operator lain."})
    await write_operator_audit(request, actor_user_id=str(user["id"]), action="community.report.review", outcome="succeeded",
        resource_type="community_report", resource_id=str(report_id), metadata={"decision": payload.decision, "reason": payload.reason, "community_id": str(report["community_id"])})
    return {"report": reviewed[0], "community_suspended": payload.decision == "suspend_community"}


# ADR-0020 — explicit, least-privilege Agent resource grants.
# These endpoints manage grants only. No Agent content/runtime route may use a grant
# until it calls the same fail-closed authorization contract for every read/write.
AGENT_RESOURCE_SCOPES = {
    "community": {"read_published_content", "create_agent_post", "comment"},
    "workspace": {"read_workspace_documents", "comment"},
}


class AgentResourceGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_type: Literal["community", "workspace"]
    resource_id: uuid.UUID
    scopes: list[Literal["read_published_content", "read_workspace_documents", "create_agent_post", "comment"]] = Field(min_length=1, max_length=4)
    expires_at: datetime | None = None


class AgentResourceGrantRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8, max_length=500)


async def _require_active_agent(agent_id: uuid.UUID) -> dict[str, Any]:
    agents = await _db("GET", "ai_agents", params={
        "select": "id,status", "id": f"eq.{agent_id}", "status": "eq.active", "limit": "1",
    })
    if not agents:
        raise HTTPException(404, detail={"code": "AGENT_NOT_ACTIVE", "message": "Agent tidak ditemukan atau tidak aktif."})
    owners = await _db("GET", "agent_ownerships", params={
        "select": "agent_id,owner_user_id", "agent_id": f"eq.{agent_id}",
        "ownership_role": "eq.owner", "status": "eq.active", "limit": "1",
    })
    if not owners:
        raise HTTPException(403, detail={"code": "AGENT_OWNER_REQUIRED", "message": "Agent harus memiliki pemilik aktif."})
    return agents[0]


async def _resource_grant_authority(resource_type: str, resource_id: uuid.UUID, user_id: str) -> None:
    if resource_type == "community":
        community = await _community(resource_id)
        membership = await _membership(resource_id, user_id)
        if not membership or membership.get("role") not in ("owner", "moderator"):
            raise HTTPException(403, detail={"code": "RESOURCE_GRANT_APPROVER_REQUIRED", "message": "Pemilik atau moderator komunitas harus menyetujui akses Agent."})
        return
    access = await _require_workspace(resource_id, user_id)
    if access["membership"].get("role") != "owner":
        raise HTTPException(403, detail={"code": "RESOURCE_GRANT_APPROVER_REQUIRED", "message": "Pemilik workspace harus menyetujui akses Agent."})


@router.post("/agents/{agent_id}/resource-grants", status_code=201)
async def create_agent_resource_grant(agent_id: uuid.UUID, payload: AgentResourceGrantCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    user_id = str(user["id"])
    await _require_active_agent(agent_id)
    await _resource_grant_authority(payload.resource_type, payload.resource_id, user_id)
    scopes = sorted(set(payload.scopes))
    invalid = set(scopes) - AGENT_RESOURCE_SCOPES[payload.resource_type]
    if invalid:
        raise HTTPException(422, detail={"code": "AGENT_GRANT_SCOPE_NOT_ALLOWED", "message": "Scope tidak tersedia untuk jenis resource ini."})
    if payload.expires_at and payload.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(422, detail={"code": "AGENT_GRANT_EXPIRY_INVALID", "message": "Masa berlaku harus berada di masa depan."})
    resource_column = "community_id" if payload.resource_type == "community" else "workspace_id"
    body = {
        "agent_id": str(agent_id), "resource_type": payload.resource_type,
        resource_column: str(payload.resource_id), "granted_by": user_id,
        "scopes": scopes, "policy_version": 1, "status": "active",
        "expires_at": payload.expires_at.astimezone(timezone.utc).isoformat() if payload.expires_at else None,
    }
    try:
        rows = await _db("POST", "agent_resource_grants", body=body, prefer="return=representation")
    except HTTPException as exc:
        if exc.status_code == 409:
            raise HTTPException(409, detail={"code": "AGENT_RESOURCE_GRANT_CONFLICT", "message": "Grant aktif sudah ada untuk Agent dan resource ini."}) from exc
        raise
    grant = rows[0]
    await _db("POST", "agent_resource_grant_audit", body={
        "grant_id": grant["id"], "agent_id": str(agent_id),
        "resource_type": payload.resource_type, "resource_id": str(payload.resource_id),
        "actor_user_id": user_id, "action": "grant_created", "scopes": scopes,
    }, prefer="return=minimal")
    return {"grant": grant, "participation_enabled": False, "notice": "Grant tercatat; runtime Agent tetap fail-closed sampai semua jalur konten menegakkan kontrak otorisasi."}


@router.get("/agents/{agent_id}/resource-grants")
async def list_agent_resource_grants(agent_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    user_id = str(user["id"])
    await _require_agent_owner(agent_id, user_id)
    rows = await _db("GET", "agent_resource_grants", params={
        "select": "*", "agent_id": f"eq.{agent_id}", "order": "created_at.desc", "limit": "200",
    })
    return {"grants": rows or []}


@router.post("/agents/{agent_id}/resource-grants/{grant_id}/revoke")
async def revoke_agent_resource_grant(agent_id: uuid.UUID, grant_id: uuid.UUID, payload: AgentResourceGrantRevoke, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    user_id = str(user["id"])
    await _require_active_agent(agent_id)
    grants = await _db("GET", "agent_resource_grants", params={
        "select": "*", "id": f"eq.{grant_id}", "agent_id": f"eq.{agent_id}", "status": "eq.active", "limit": "1",
    })
    if not grants:
        raise HTTPException(404, detail={"code": "AGENT_RESOURCE_GRANT_NOT_FOUND", "message": "Grant aktif tidak ditemukan."})
    grant = grants[0]
    resource_id = grant.get("community_id") if grant["resource_type"] == "community" else grant.get("workspace_id")
    await _resource_grant_authority(grant["resource_type"], uuid.UUID(resource_id), user_id)
    now = datetime.now(timezone.utc).isoformat()
    rows = await _db("PATCH", "agent_resource_grants", params={"id": f"eq.{grant_id}", "status": "eq.active"}, body={
        "status": "revoked", "revoked_at": now, "revoked_by": user_id,
        "revocation_reason": payload.reason, "updated_at": now,
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "AGENT_RESOURCE_GRANT_CONFLICT", "message": "Grant berubah saat dicabut; muat ulang."})
    await _db("POST", "agent_resource_grant_audit", body={
        "grant_id": str(grant_id), "agent_id": str(agent_id),
        "resource_type": grant["resource_type"], "resource_id": resource_id,
        "actor_user_id": user_id, "action": "grant_revoked", "scopes": grant.get("scopes", []),
        "reason": payload.reason,
    }, prefer="return=minimal")
    return {"grant": rows[0], "participation_enabled": False}
