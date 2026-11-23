"""Tenant-scoped organization repository and application service (ENG-P02)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

from allpha_api.auth import service_db_request, user_db_request


@dataclass(frozen=True, slots=True)
class OrganizationActor:
    """Trusted caller context derived only from the verified FastAPI session."""

    user_id: str
    access_token: str

    @classmethod
    def from_request(cls, request: Request, user: dict[str, Any]) -> "OrganizationActor":
        trusted_user_id = getattr(request.state, "user_id", None)
        access_token = getattr(request.state, "supabase_access_token", None)
        supplied_user_id = str(user.get("id") or "")
        if not trusted_user_id or str(trusted_user_id) != supplied_user_id:
            raise HTTPException(
                status_code=401,
                detail={"code": "IDENTITY_MISMATCH", "message": "Identitas actor tidak cocok dengan sesi terverifikasi."},
            )
        if not access_token:
            raise HTTPException(
                status_code=401,
                detail={"code": "AUTH_CONTEXT_MISSING", "message": "Konteks sesi terverifikasi tidak tersedia."},
            )
        try:
            return cls(user_id=str(uuid.UUID(supplied_user_id)), access_token=str(access_token))
        except (ValueError, TypeError, AttributeError) as exc:
            raise HTTPException(
                status_code=401,
                detail={"code": "IDENTITY_INVALID", "message": "Identitas actor tidak valid."},
            ) from exc


class OrganizationRepository:
    """Only data-access layer for organization rows and privileged tenant commands."""

    async def list_actor_memberships(self, actor: OrganizationActor) -> list[dict[str, Any]]:
        rows = await user_db_request(
            "GET",
            "organization_memberships",
            actor.access_token,
            params={
                "select": "organization_id,user_id,role,created_at",
                "user_id": f"eq.{actor.user_id}",
                "order": "created_at.desc",
                "limit": "100",
            },
        )
        return rows if isinstance(rows, list) else []

    async def list_organizations(
        self, actor: OrganizationActor, organization_ids: set[str]
    ) -> list[dict[str, Any]]:
        if not organization_ids:
            return []
        return await user_db_request(
            "GET",
            "organizations",
            actor.access_token,
            params={
                "select": "id,name,slug,owner_id,created_at,updated_at",
                "id": f"in.({','.join(sorted(organization_ids))})",
                "order": "created_at.desc",
                "limit": "100",
            },
        )

    async def list_tenant_memberships(
        self, actor: OrganizationActor, organization_id: str
    ) -> list[dict[str, Any]]:
        rows = await user_db_request(
            "GET",
            "organization_memberships",
            actor.access_token,
            params={
                "select": "organization_id,user_id,role,invited_by,created_at",
                "organization_id": f"eq.{organization_id}",
                "order": "created_at.asc",
                "limit": "500",
            },
        )
        return rows if isinstance(rows, list) else []

    async def create_organization(
        self, actor: OrganizationActor, *, name: str, slug: str
    ) -> Any:
        return await service_db_request(
            "create_organization_for_user",
            body={"p_actor_user_id": actor.user_id, "p_name": name, "p_slug": slug},
        )

    async def add_member(
        self, actor: OrganizationActor, *, organization_id: str, target_user_id: str, role: str
    ) -> Any:
        return await service_db_request(
            "add_organization_member_for_actor",
            body={
                "p_organization_id": organization_id,
                "p_actor_user_id": actor.user_id,
                "p_target_user_id": target_user_id,
                "p_role": role,
            },
        )

    async def update_member_role(
        self, actor: OrganizationActor, *, organization_id: str, target_user_id: str, role: str
    ) -> Any:
        return await service_db_request(
            "update_organization_member_role_for_actor",
            body={
                "p_organization_id": organization_id,
                "p_actor_user_id": actor.user_id,
                "p_target_user_id": target_user_id,
                "p_role": role,
            },
        )

    async def remove_member(
        self, actor: OrganizationActor, *, organization_id: str, target_user_id: str
    ) -> Any:
        return await service_db_request(
            "remove_organization_member_for_actor",
            body={
                "p_organization_id": organization_id,
                "p_actor_user_id": actor.user_id,
                "p_target_user_id": target_user_id,
            },
        )


class OrganizationService:
    """Tenant-scoped application rules; re-check scope after every repository read."""

    def __init__(self, repository: OrganizationRepository | None = None) -> None:
        self.repository = repository or OrganizationRepository()

    async def list_for_actor(self, actor: OrganizationActor) -> list[dict[str, Any]]:
        memberships = await self.repository.list_actor_memberships(actor)
        organization_ids: set[str] = set()
        for row in memberships:
            if str(row.get("user_id") or "") != actor.user_id:
                continue
            try:
                organization_ids.add(str(uuid.UUID(str(row.get("organization_id") or ""))))
            except (ValueError, TypeError, AttributeError):
                continue
        if not organization_ids:
            return []
        rows = await self.repository.list_organizations(actor, organization_ids)
        return [
            row for row in rows
            if str(row.get("id") or "") in organization_ids
        ]

    async def list_memberships(
        self,
        actor: OrganizationActor,
        organization_id: str,
        actor_membership: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if (
            str(actor_membership.get("organization_id") or "") != organization_id
            or str(actor_membership.get("user_id") or "") != actor.user_id
        ):
            raise HTTPException(
                status_code=404,
                detail={"code": "ORGANIZATION_NOT_FOUND", "message": "Organisasi tidak ditemukan."},
            )
        rows = await self.repository.list_tenant_memberships(actor, organization_id)
        is_admin = actor_membership.get("role") in {"owner", "admin"}
        return [
            row for row in rows
            if str(row.get("organization_id") or "") == organization_id
            and (is_admin or str(row.get("user_id") or "") == actor.user_id)
        ]

    async def create(
        self, actor: OrganizationActor, *, name: str, slug: str
    ) -> dict[str, Any]:
        rows = await self.repository.create_organization(actor, name=name, slug=slug)
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or str(rows[0].get("owner_id") or "") != actor.user_id
        ):
            raise HTTPException(
                status_code=500,
                detail={"code": "CREATE_FAILED", "message": "Organisasi tidak dapat dibuat."},
            )
        return rows[0]

    async def add_member(
        self, actor: OrganizationActor, *, organization_id: str, target_user_id: str, role: str
    ) -> dict[str, Any]:
        rows = await self.repository.add_member(
            actor, organization_id=organization_id, target_user_id=target_user_id, role=role
        )
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or str(rows[0].get("organization_id") or "") != organization_id
            or str(rows[0].get("user_id") or "") != target_user_id
            or str(rows[0].get("role") or "") != role
            or str(rows[0].get("invited_by") or "") != actor.user_id
        ):
            raise HTTPException(
                status_code=500,
                detail={"code": "MEMBERSHIP_CREATE_FAILED", "message": "Keanggotaan tidak dapat dibuat."},
            )
        return rows[0]

    async def update_member_role(
        self, actor: OrganizationActor, *, organization_id: str, target_user_id: str, role: str
    ) -> dict[str, Any]:
        rows = await self.repository.update_member_role(
            actor, organization_id=organization_id, target_user_id=target_user_id, role=role
        )
        if not isinstance(rows, list) or not rows:
            raise HTTPException(
                status_code=404,
                detail={"code": "ORGANIZATION_MEMBER_NOT_FOUND", "message": "Anggota organisasi tidak ditemukan."},
            )
        if (
            len(rows) != 1
            or str(rows[0].get("organization_id") or "") != organization_id
            or str(rows[0].get("user_id") or "") != target_user_id
            or str(rows[0].get("role") or "") != role
        ):
            raise HTTPException(
                status_code=500,
                detail={"code": "ORGANIZATION_MEMBER_SCOPE_MISMATCH", "message": "Respons keanggotaan tidak sesuai dengan organisasi yang diminta."},
            )
        return rows[0]

    async def remove_member(
        self, actor: OrganizationActor, *, organization_id: str, target_user_id: str
    ) -> None:
        removed = await self.repository.remove_member(
            actor, organization_id=organization_id, target_user_id=target_user_id
        )
        if removed is not True:
            raise HTTPException(
                status_code=404,
                detail={"code": "ORGANIZATION_MEMBER_NOT_FOUND", "message": "Anggota organisasi tidak ditemukan."},
            )


organization_service = OrganizationService()
