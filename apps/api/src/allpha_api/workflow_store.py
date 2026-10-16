"""Server-only Supabase/PostgREST persistence adapter for ENG-P11."""
from __future__ import annotations

import os
from typing import Any

import httpx

from allpha_api.workflow_engine import WorkflowDefinition, build_step_specs


class WorkflowPersistenceError(RuntimeError):
    """Workflow state could not be confirmed durably."""


class WorkflowStore:
    _TIMEOUT = httpx.Timeout(10.0, connect=3.0)

    def __init__(self, *, supabase_url: str, service_key: str,
                 transport: httpx.AsyncBaseTransport | None = None):
        if not supabase_url.strip() or not service_key.strip():
            raise ValueError("Supabase URL and service-role key are required")
        self._base_url = supabase_url.rstrip("/")
        self._key = service_key
        self._transport = transport

    @classmethod
    def from_environment(cls, *, transport: httpx.AsyncBaseTransport | None = None) -> "WorkflowStore":
        url, key = os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise ValueError("Workflow persistence requires server-side Supabase configuration")
        return cls(supabase_url=url, service_key=key, transport=transport)

    async def request(self, method: str, path: str, *, params: dict[str, str] | None = None,
                      body: dict[str, Any] | None = None, prefer: str | None = None) -> Any:
        headers = {"apikey": self._key, "Authorization": f"Bearer {self._key}",
                   "Content-Type": "application/json", "Accept": "application/json"}
        if prefer:
            headers["Prefer"] = prefer
        try:
            async with httpx.AsyncClient(timeout=self._TIMEOUT, transport=self._transport) as client:
                response = await client.request(method, f"{self._base_url}/rest/v1/{path}",
                                                headers=headers, params=params, json=body)
        except httpx.HTTPError as exc:
            raise WorkflowPersistenceError("workflow persistence unavailable; outcome may be unknown") from exc
        if response.status_code >= 400:
            if response.status_code in (401, 403):
                raise WorkflowPersistenceError("workflow persistence permission denied")
            if response.status_code >= 500:
                raise WorkflowPersistenceError("workflow database unavailable")
            raise WorkflowPersistenceError(f"workflow persistence rejected request (HTTP {response.status_code})")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise WorkflowPersistenceError("workflow persistence returned invalid JSON") from exc

    async def create_definition(self, body: dict[str, Any]) -> dict[str, Any]:
        rows = await self.request("POST", "workflow_definitions", params={"select": "*"},
                                  body=body, prefer="return=representation")
        if not rows:
            raise WorkflowPersistenceError("workflow definition insert was not confirmed")
        return rows[0]

    async def get_definition(self, owner_id: str, definition_id: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "workflow_definitions", params={
            "select": "*", "id": f"eq.{definition_id}", "owner_user_id": f"eq.{owner_id}", "limit": "1"})
        return rows[0] if rows else None

    async def list_definitions(self, owner_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return await self.request("GET", "workflow_definitions", params={
            "select": "id,owner_user_id,workflow_key,version,digest,status,created_at",
            "owner_user_id": f"eq.{owner_id}", "order": "created_at.desc",
            "limit": str(max(1, min(limit, 100)))}) or []

    async def create_run(self, owner_id: str, definition: dict[str, Any], input_payload: dict[str, Any],
                         trace_id: str) -> dict[str, Any]:
        rows = await self.request("POST", "rpc/create_workflow_run", body={
            "p_owner_user_id": owner_id, "p_definition_id": definition["id"],
            "p_input_payload": input_payload, "p_trace_id": trace_id,
            "p_step_specs": build_step_specs(WorkflowDefinition.model_validate(definition["definition"])),
        })
        if not rows:
            raise WorkflowPersistenceError("workflow run creation was not confirmed")
        return rows[0]

    async def get_run(self, owner_id: str, run_id: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "workflow_runs", params={
            "select": "*", "id": f"eq.{run_id}", "owner_user_id": f"eq.{owner_id}", "limit": "1"})
        if not rows:
            return None
        run = rows[0]
        run["steps"] = await self.request("GET", "workflow_steps", params={
            "select": "*", "run_id": f"eq.{run_id}", "owner_user_id": f"eq.{owner_id}",
            "order": "created_at.asc", "limit": "100"})
        run["events"] = await self.request("GET", "workflow_run_events", params={
            "select": "sequence,event_type,step_key,details,created_at",
            "run_id": f"eq.{run_id}", "owner_user_id": f"eq.{owner_id}",
            "order": "sequence.asc", "limit": "200"})
        return run

    async def list_runs(self, owner_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return await self.request("GET", "workflow_runs", params={
            "select": "id,owner_user_id,definition_id,definition_version,status,trace_id,created_at,updated_at,completed_at",
            "owner_user_id": f"eq.{owner_id}", "order": "created_at.desc",
            "limit": str(max(1, min(limit, 100)))}) or []

    async def cancel_run(self, owner_id: str, run_id: str) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/cancel_workflow_run", body={
            "p_run_id": run_id, "p_owner_user_id": owner_id})
        return rows[0] if rows else None

    async def claim_step(self, owner_id: str, run_id: str, lease_token: str, *, lease_seconds: int = 30) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/claim_workflow_step", body={
            "p_run_id": run_id, "p_owner_user_id": owner_id,
            "p_lease_token": lease_token, "p_lease_seconds": lease_seconds,
        })
        return rows[0] if rows else None

    async def finalize_step(self, *, owner_id: str, run_id: str, step_id: str, lease_token: str,
                            terminal_state: str, output_payload: dict[str, Any] | None,
                            error_code: str | None, checkpoint: dict[str, Any] | None) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/finalize_workflow_step", body={
            "p_run_id": run_id, "p_owner_user_id": owner_id, "p_step_id": step_id,
            "p_lease_token": lease_token, "p_terminal_state": terminal_state,
            "p_output_payload": output_payload, "p_error_code": error_code, "p_checkpoint": checkpoint,
        })
        return rows[0] if rows else None

    async def timeout_run(self, owner_id: str, run_id: str) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/timeout_workflow_run", body={
            "p_run_id": run_id, "p_owner_user_id": owner_id,
        })
        return rows[0] if rows else None
