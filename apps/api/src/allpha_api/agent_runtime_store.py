"""Server-only Supabase persistence for ENG-P10 runtime sessions and tasks.

All requests use the service-role key inside FastAPI only. Callers must pass the
owner ID obtained from verified Supabase Auth; client applications never receive
the credential or write directly to runtime tables.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
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
            "select": "id,agent_id,capability_key,required_permission_scopes,risk_level,status,policy_version,runtime_policy_id,updated_at",
            "agent_id": f"eq.{agent_id}", "capability_key": f"eq.{tool_key}",
            "status": "eq.approved", "limit": "1",
        })
        return rows[0] if rows and rows[0].get("policy_version") else None

    async def get_approved_runtime_policy(self, agent_id: str, policy_id: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "agent_runtime_policies", params={
            "select": "id,agent_id,policy_version,policy_document,policy_digest,approved_tool_keys,required_permission_scopes,risk_constraints,status,approved_at",
            "id": f"eq.{policy_id}", "agent_id": f"eq.{agent_id}", "status": "eq.approved", "limit": "1",
        })
        return rows[0] if rows else None

    async def claim_task(self, owner_id: str, task_id: str, lease_token: str,
                         *, lease_seconds: int = 60) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/claim_agent_runtime_task", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id,
            "p_lease_token": lease_token, "p_lease_seconds": lease_seconds,
        })
        return rows[0] if rows else None

    async def heartbeat_task(self, owner_id: str, task_id: str, lease_token: str,
                             task_version: int, *, lease_seconds: int = 60) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/heartbeat_agent_runtime_task", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id,
            "p_lease_token": lease_token, "p_task_version": task_version,
            "p_lease_seconds": lease_seconds,
        })
        return rows[0] if rows else None

    async def mark_unknown_effect(self, owner_id: str, task_id: str) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/mark_agent_runtime_effect_unknown", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id,
        })
        return rows[0] if rows else None

    async def append_checkpoint(self, owner_id: str, task_id: str, lease_token: str, task_version: int,
                                sequence: int, step_key: str, input_fingerprint: str,
                                checkpoint_hash: str, result_payload: dict[str, Any]) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/append_agent_runtime_checkpoint", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id, "p_lease_token": lease_token,
            "p_task_version": task_version, "p_sequence": sequence, "p_step_key": step_key,
            "p_input_fingerprint": input_fingerprint, "p_checkpoint_hash": checkpoint_hash,
            "p_result_payload": result_payload,
        })
        return rows[0] if rows else None

    async def get_latest_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "agent_runtime_checkpoints", params={
            "select": "task_id,task_version,sequence,step_key,input_fingerprint,checkpoint_hash,result_payload,created_at",
            "task_id": f"eq.{task_id}", "order": "sequence.desc", "limit": "1",
        })
        return rows[0] if rows else None

    async def list_checkpoints(self, task_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
        return await self.request("GET", "agent_runtime_checkpoints", params={
            "select": "task_id,task_version,sequence,step_key,input_fingerprint,checkpoint_hash,result_payload,created_at",
            "task_id": f"eq.{task_id}", "order": "sequence.asc",
            "limit": str(max(1, min(limit, 5))),
        }) or []

    async def begin_effect(self, owner_id: str, task_id: str, lease_token: str, task_version: int,
                          step_key: str, idempotency_key: str, input_fingerprint: str) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/begin_agent_runtime_effect", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id, "p_lease_token": lease_token,
            "p_task_version": task_version, "p_step_key": step_key,
            "p_idempotency_key": idempotency_key, "p_input_fingerprint": input_fingerprint,
        })
        return rows[0] if rows else None

    async def complete_effect(self, owner_id: str, task_id: str, lease_token: str, task_version: int,
                              step_key: str, idempotency_key: str, input_fingerprint: str,
                              result_payload: dict[str, Any]) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/complete_agent_runtime_effect", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id, "p_lease_token": lease_token,
            "p_task_version": task_version, "p_step_key": step_key,
            "p_idempotency_key": idempotency_key, "p_input_fingerprint": input_fingerprint,
            "p_result_payload": result_payload,
        })
        return rows[0] if rows else None

    async def finalize_task(self, owner_id: str, task_id: str, lease_token: str, task_version: int,
                            *, state: str, output_payload: dict[str, Any] | None,
                            error_code: str | None, event_log: list[dict[str, Any]]) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/finalize_agent_runtime_task", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id, "p_lease_token": lease_token,
            "p_task_version": task_version, "p_terminal_state": state,
            "p_output_payload": output_payload, "p_error_code": error_code, "p_event_log": event_log,
        })
        return rows[0] if rows else None

    async def append_execution_event(self, owner_id: str, task_id: str, lease_token: str,
                                     task_version: int, event: dict[str, Any]) -> dict[str, Any] | None:
        state = str(event.get("state") or "")
        reason = event.get("reason_code")
        details: dict[str, Any] = {}
        if isinstance(reason, str) and reason:
            details["reason_code"] = reason[:120]
        event_type = event.get("event_type")
        if event_type not in {"state_transition", "checkpoint_resumed", "execution_reconciled"}:
            event_type = "state_transition"
        rows = await self.request("POST", "rpc/append_agent_runtime_execution_event", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id,
            "p_lease_token": lease_token, "p_task_version": task_version,
            "p_event_type": event_type, "p_state": state,
            "p_step_key": str(event.get("step_key") or ("tool:" + str(event.get("tool_key") or "runtime")))[:160],
            "p_details": details,
        })
        return rows[0] if rows else None

    async def list_execution_events(self, owner_id: str, task_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        return await self.request("GET", "agent_runtime_execution_events", params={
            "select": "id,task_id,sequence,task_version,trace_id,event_type,state,step_key,details,created_at",
            "owner_user_id": f"eq.{owner_id}", "task_id": f"eq.{task_id}",
            "order": "sequence.asc", "limit": str(max(1, min(limit, 500))),
        }) or []

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

    async def list_runnable_planned_tasks(self, *, limit: int = 10) -> list[dict[str, Any]]:
        """Return due created/queued/retrying or lease-expired planned tasks."""
        bounded_limit = max(1, min(limit, 25))
        plan_filter = {"input_payload->>_runtime_plan_version": "eq.1"}
        now = datetime.now(timezone.utc).isoformat()
        due = await self.request("GET", "agent_runtime_tasks", params={
            "select": "*", "state": "in.(created,queued,retrying)",
            "or": f"(next_attempt_at.is.null,next_attempt_at.lte.{now})",
            **plan_filter, "order": "created_at.asc", "limit": str(bounded_limit),
        }) or []
        expired = await self.request("GET", "agent_runtime_tasks", params={
            "select": "*", "state": "eq.executing", "lease_expires_at": f"lte.{now}",
            **plan_filter, "order": "created_at.asc", "limit": str(bounded_limit),
        }) or []
        by_id = {str(row.get("id")): row for row in [*due, *expired] if row.get("id")}
        return sorted(by_id.values(), key=lambda row: str(row.get("created_at") or ""))[:bounded_limit]

    async def schedule_retry_task(self, owner_id: str, task_id: str, lease_token: str,
                                  task_version: int, *, error_code: str,
                                  retry_after_seconds: int, output_payload: dict[str, Any] | None,
                                  event_log: list[dict[str, Any]]) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/schedule_agent_runtime_retry", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id,
            "p_lease_token": lease_token, "p_task_version": task_version,
            "p_error_code": error_code, "p_retry_after_seconds": retry_after_seconds,
            "p_output_payload": output_payload, "p_event_log": event_log,
        })
        return rows[0] if rows else None

    async def reap_retry_exhaustion(self) -> int:
        result = await self.request("POST", "rpc/reap_agent_runtime_retry_exhaustion", body={})
        return int(result or 0)

    async def fail_unclaimed_task(self, owner_id: str, task_id: str, task_version: int,
                                  error_code: str) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/fail_unclaimed_agent_runtime_task", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id,
            "p_task_version": task_version, "p_error_code": error_code,
        })
        return rows[0] if rows else None

    async def list_agent_tasks(self, owner_id: str, agent_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return await self.request("GET", "agent_runtime_tasks", params={
            "select": "id,session_id,agent_id,skill_id,agent_version,skill_version,state,tool_key,trace_id,created_at,updated_at,completed_at,error_code,execution_event_seq",
            "owner_user_id": f"eq.{owner_id}", "agent_id": f"eq.{agent_id}",
            "order": "created_at.desc", "limit": str(max(1, min(limit, 100))),
        }) or []

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

    async def create_tool_plan_reservation(self, body: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        rows = await self.request(
            "POST", "agent_runtime_tool_plans", params={"select": "*"}, body=body,
            prefer="resolution=ignore-duplicates,return=representation",
        )
        if rows:
            return rows[0], True
        existing = await self.find_tool_plan_by_idempotency(
            str(body["owner_user_id"]), str(body["idempotency_key"])
        )
        if not existing:
            raise AgentRuntimePersistenceError("tool-plan reservation was not confirmed")
        return existing, False

    async def find_tool_plan_by_idempotency(self, owner_id: str, key: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "agent_runtime_tool_plans", params={
            "select": "*", "owner_user_id": f"eq.{owner_id}",
            "idempotency_key": f"eq.{key}", "limit": "1",
        })
        return rows[0] if rows else None

    async def get_tool_plan(self, owner_id: str, plan_id: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "agent_runtime_tool_plans", params={
            "select": "*", "id": f"eq.{plan_id}", "owner_user_id": f"eq.{owner_id}", "limit": "1",
        })
        return rows[0] if rows else None

    async def update_tool_plan(self, owner_id: str, plan_id: str, body: dict[str, Any],
                               *, expected_status: str = "planning") -> dict[str, Any] | None:
        rows = await self.request("PATCH", "agent_runtime_tool_plans", params={
            "select": "*", "id": f"eq.{plan_id}", "owner_user_id": f"eq.{owner_id}",
            "status": f"eq.{expected_status}",
        }, body=body, prefer="return=representation")
        return rows[0] if rows else None

    async def mark_tool_plan_used(self, owner_id: str, plan_id: str, task_id: str) -> dict[str, Any] | None:
        rows = await self.request("PATCH", "agent_runtime_tool_plans", params={
            "select": "*", "id": f"eq.{plan_id}", "owner_user_id": f"eq.{owner_id}",
            "status": "eq.completed",
        }, body={"status": "used", "task_id": task_id, "updated_at": datetime.now(timezone.utc).isoformat()},
           prefer="return=representation")
        if rows:
            return rows[0]
        existing = await self.get_tool_plan(owner_id, plan_id)
        if existing and existing.get("status") == "used" and str(existing.get("task_id")) == task_id:
            return existing
        return None
