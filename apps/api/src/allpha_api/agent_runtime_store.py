"""Server-only Supabase persistence for ENG-P10 runtime sessions and tasks.

All requests use the service-role key inside FastAPI only. Callers must pass the
owner ID obtained from verified Supabase Auth; client applications never receive
the credential or write directly to runtime tables.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


class AgentRuntimePersistenceError(RuntimeError):
    """Runtime persistence is unavailable or did not confirm a durable result."""


class AgentRuntimeStore:
    _TIMEOUT = httpx.Timeout(10.0, connect=3.0)

    def __init__(self, *, supabase_url: str, service_key: str,
                 transport: httpx.AsyncBaseTransport | None = None):
        if not supabase_url.strip() or not service_key.strip():
            raise ValueError("Supabase URL and service-role key are required")
        self._base_url = supabase_url.rstrip("/")
        self._key = service_key
        self._transport = transport

    @classmethod
    def from_environment(cls, *, transport: httpx.AsyncBaseTransport | None = None) -> "AgentRuntimeStore":
        url, key = os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise ValueError("Runtime persistence requires server-side Supabase configuration")
        return cls(supabase_url=url, service_key=key, transport=transport)

    async def request(self, method: str, path: str, *, params: dict[str, str] | None = None,
                      body: dict[str, Any] | None = None, prefer: str | None = None) -> Any:
        headers = {
            "apikey": self._key, "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json", "Accept": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        try:
            async with httpx.AsyncClient(timeout=self._TIMEOUT, transport=self._transport) as client:
                response = await client.request(
                    method, f"{self._base_url}/rest/v1/{path}",
                    headers=headers, params=params, json=body,
                )
        except httpx.HTTPError as exc:
            raise AgentRuntimePersistenceError("Agent runtime persistence is unavailable; outcome may be unknown") from exc
        if response.status_code >= 400:
            if response.status_code == 409:
                raise AgentRuntimePersistenceError("runtime idempotency key conflicts with existing data")
            if response.status_code in (401, 403):
                raise AgentRuntimePersistenceError("runtime persistence permission was denied")
            if response.status_code >= 500:
                raise AgentRuntimePersistenceError("runtime database is unavailable")
            raise AgentRuntimePersistenceError(f"runtime persistence rejected the operation (HTTP {response.status_code})")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise AgentRuntimePersistenceError("runtime persistence returned invalid JSON") from exc

    async def owner_has_agent(self, owner_id: str, agent_id: str) -> bool:
        rows = await self.request("GET", "agent_ownerships", params={
            "select": "agent_id", "agent_id": f"eq.{agent_id}",
            "owner_user_id": f"eq.{owner_id}", "ownership_role": "eq.owner",
            "status": "eq.active", "limit": "1",
        })
        return bool(rows)

    async def get_agent(self, owner_id: str, agent_id: str) -> dict[str, Any] | None:
        if not await self.owner_has_agent(owner_id, agent_id):
            return None
        rows = await self.request("GET", "ai_agents", params={
            "select": "id,version,status,created_by,updated_at",
            "id": f"eq.{agent_id}", "limit": "1",
        })
        return rows[0] if rows else None

    async def get_skill(self, owner_id: str, agent_id: str, skill_id: str) -> dict[str, Any] | None:
        if not await self.owner_has_agent(owner_id, agent_id):
            return None
        rows = await self.request("GET", "agent_skills", params={
            "select": "id,agent_id,version,status,tool_dependencies,required_permission_scopes,budget_limits",
            "id": f"eq.{skill_id}", "agent_id": f"eq.{agent_id}", "limit": "1",
        })
        return rows[0] if rows else None

    async def get_approved_capability(self, agent_id: str, tool_key: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "agent_capabilities", params={
            "select": "id,capability_key,required_permission_scopes,risk_level,status,policy_version,updated_at",
            "agent_id": f"eq.{agent_id}", "capability_key": f"eq.{tool_key}",
            "status": "eq.approved", "limit": "1",
        })
        return rows[0] if rows and rows[0].get("policy_version") else None

    async def create_session(self, body: dict[str, Any]) -> dict[str, Any]:
        rows = await self.request("POST", "agent_runtime_sessions",
                                  params={"select": "*"}, body=body, prefer="return=representation")
        if not rows:
            raise AgentRuntimePersistenceError("session creation was not confirmed")
        return rows[0]

    async def list_sessions(self, owner_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return await self.request("GET", "agent_runtime_sessions", params={
            "select": "id,owner_user_id,agent_id,title,status,last_activity_at,created_at,updated_at",
            "owner_user_id": f"eq.{owner_id}", "order": "last_activity_at.desc",
            "limit": str(max(1, min(limit, 100))),
        }) or []

    async def get_session(self, owner_id: str, session_id: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "agent_runtime_sessions", params={
            "select": "*", "id": f"eq.{session_id}", "owner_user_id": f"eq.{owner_id}", "limit": "1",
        })
        return rows[0] if rows else None

    async def create_task(self, body: dict[str, Any]) -> dict[str, Any]:
        rows = await self.request("POST", "agent_runtime_tasks",
                                  params={"select": "*"}, body=body, prefer="return=representation")
        if not rows:
            raise AgentRuntimePersistenceError("task creation was not confirmed")
        return rows[0]

    async def get_task(self, owner_id: str, task_id: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "agent_runtime_tasks", params={
            "select": "*", "id": f"eq.{task_id}", "owner_user_id": f"eq.{owner_id}", "limit": "1",
        })
        return rows[0] if rows else None

    async def list_tasks(self, owner_id: str, session_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return await self.request("GET", "agent_runtime_tasks", params={
            "select": "id,session_id,agent_id,skill_id,state,tool_key,trace_id,created_at,updated_at,completed_at,error_code",
            "owner_user_id": f"eq.{owner_id}", "session_id": f"eq.{session_id}",
            "order": "created_at.desc", "limit": str(max(1, min(limit, 100))),
        }) or []

    async def update_task(self, owner_id: str, task_id: str, body: dict[str, Any],
                          *, expected_state: str | None = None) -> dict[str, Any] | None:
        params = {"id": f"eq.{task_id}", "owner_user_id": f"eq.{owner_id}", "select": "*"}
        if expected_state:
            params["state"] = f"eq.{expected_state}"
        rows = await self.request("PATCH", "agent_runtime_tasks", params=params,
                                  body=body, prefer="return=representation")
        return rows[0] if rows else None

    async def find_task_by_idempotency(self, owner_id: str, key: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "agent_runtime_tasks", params={
            "select": "*", "owner_user_id": f"eq.{owner_id}",
            "idempotency_key": f"eq.{key}", "limit": "1",
        })
        return rows[0] if rows else None
