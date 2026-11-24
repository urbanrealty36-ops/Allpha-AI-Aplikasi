"""Server-only Supabase persistence for ENG-P10 runtime sessions and tasks.

All requests use the service-role key inside FastAPI only. Callers must pass the
owner ID obtained from verified Supabase Auth; client applications never receive
the credential or write directly to runtime tables.
"""
from __future__ import annotations

import os
import uuid
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

    async def get_skill(
        self, owner_id: str, agent_id: str, skill_id: str, *, version: int | None = None,
    ) -> dict[str, Any] | None:
        """Resolve a published Skill, pinned to its immutable snapshot when version is supplied."""
        if not await self.owner_has_agent(owner_id, agent_id):
            return None
        # Installed Skills remain executable only while their explicit license
        # acceptance is active and has not expired. Native/public clients cannot
        # bypass this gate by pinning an older immutable Skill version.
        installations = await self.request("GET", "agent_skill_installations", params={
            "select": "id,status,license_expires_at,license_terms_digest,accepted_at",
            "agent_id": f"eq.{agent_id}", "installed_skill_id": f"eq.{skill_id}", "limit": "1",
        })
        if installations:
            installation = installations[0]
            if installation.get("status") != "active" or not installation.get("license_terms_digest") or not installation.get("accepted_at"):
                return None
            expires_at = installation.get("license_expires_at")
            if expires_at:
                try:
                    expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                except (TypeError, ValueError):
                    return None
                if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
                    return None
        if version is not None:
            snapshots = await self.request("GET", "agent_skill_versions", params={
                "select": "snapshot", "skill_id": f"eq.{skill_id}",
                "agent_id": f"eq.{agent_id}", "version": f"eq.{version}", "limit": "1",
            })
            snapshot = snapshots[0].get("snapshot") if snapshots else None
            if not isinstance(snapshot, dict):
                return None
            if (snapshot.get("id") != skill_id or snapshot.get("agent_id") != agent_id
                    or int(snapshot.get("version") or 0) != version
                    or snapshot.get("status") != "published"):
                return None
            return snapshot
        rows = await self.request("GET", "agent_skills", params={
            "select": "*", "id": f"eq.{skill_id}", "agent_id": f"eq.{agent_id}",
            "status": "eq.published", "limit": "1",
        })
        return rows[0] if rows else None

    async def get_approved_capability(self, agent_id: str, tool_key: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "agent_capabilities", params={
            "select": "id,agent_id,capability_key,required_permission_scopes,risk_level,status,policy_version,runtime_policy_id,updated_at",
            "agent_id": f"eq.{agent_id}", "capability_key": f"eq.{tool_key}",
            "status": "eq.approved", "limit": "1",
        })
        return rows[0] if rows and rows[0].get("policy_version") else None

    async def validate_knowledge_context_refs(
        self, owner_id: str, agent_id: str, refs: list[dict[str, Any]],
    ) -> bool:
        """Revalidate current owner/Agent source and chunk versions before tool execution."""
        if not refs:
            return True
        if not isinstance(refs, list) or len(refs) > 8:
            raise AgentRuntimePersistenceError("Knowledge citation reference list is invalid")
        source_ids: set[str] = set()
        chunk_ids: set[str] = set()
        for ref in refs:
            if not isinstance(ref, dict):
                raise AgentRuntimePersistenceError("Knowledge citation reference is malformed")
            try:
                source_id = str(uuid.UUID(str(ref.get("source_id") or "")))
                chunk_id = str(uuid.UUID(str(ref.get("chunk_id") or "")))
            except (ValueError, TypeError, AttributeError) as exc:
                raise AgentRuntimePersistenceError("Knowledge citation source/chunk ID is invalid") from exc
            source_ids.add(source_id)
            chunk_ids.add(chunk_id)
        sources = await self.request("GET", "agent_knowledge_sources", params={
            "select": "id,owner_id,agent_id,source_version,status,sensitivity",
            "id": "in.(" + ",".join(sorted(source_ids)) + ")",
            "owner_id": f"eq.{owner_id}",
            "agent_id": f"eq.{agent_id}",
            "status": "eq.ready",
        })
        chunks = await self.request("GET", "agent_knowledge_chunks", params={
            "select": "id,source_id,owner_id,agent_id,source_version,content_sha256",
            "id": "in.(" + ",".join(sorted(chunk_ids)) + ")",
            "owner_id": f"eq.{owner_id}",
            "agent_id": f"eq.{agent_id}",
        })
        if not isinstance(sources, list) or not isinstance(chunks, list):
            raise AgentRuntimePersistenceError("Knowledge citation verification returned invalid data")
        source_map = {str(row.get("id")): row for row in sources if isinstance(row, dict)}
        chunk_map = {str(row.get("id")): row for row in chunks if isinstance(row, dict)}
        for ref in refs:
            source = source_map.get(ref["source_id"])
            chunk = chunk_map.get(ref["chunk_id"])
            if (
                not source or not chunk
                or source.get("owner_id") != owner_id or source.get("agent_id") != agent_id
                or source.get("status") != "ready"
                or source.get("source_version") != ref.get("source_version")
                or source.get("sensitivity") != ref.get("sensitivity")
                or chunk.get("owner_id") != owner_id or chunk.get("agent_id") != agent_id
                or chunk.get("source_id") != ref.get("source_id")
                or chunk.get("source_version") != ref.get("source_version")
                or chunk.get("content_sha256") != ref.get("content_sha256")
            ):
                return False
        return True

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

    async def list_checkpoints(self, task_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """Read at most ten checkpoints (request + result for each of five native tool calls)."""
        return await self.request("GET", "agent_runtime_checkpoints", params={
            "select": "task_id,task_version,sequence,step_key,input_fingerprint,checkpoint_hash,result_payload,created_at",
            "task_id": f"eq.{task_id}", "order": "sequence.asc",
            "limit": str(max(1, min(limit, 10))),
        }) or []

    async def get_effect_receipt(self, task_id: str, step_key: str,
                                 idempotency_key: str) -> dict[str, Any] | None:
        rows = await self.request("GET", "agent_runtime_effect_receipts", params={
            "select": "task_id,task_version,step_key,idempotency_key,input_fingerprint,status,result_payload,started_at,completed_at,updated_at",
            "task_id": f"eq.{task_id}", "step_key": f"eq.{step_key}",
            "idempotency_key": f"eq.{idempotency_key}", "limit": "1",
        })
        return rows[0] if rows else None

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

    async def runtime_schema_readiness(self) -> dict[str, Any]:
        result = await self.request("POST", "rpc/agent_runtime_worker_schema_readiness", body={})
        if not isinstance(result, dict) or not isinstance(result.get("ready"), bool):
            raise AgentRuntimePersistenceError("runtime worker schema readiness response is invalid")
        if result["ready"] is not True:
            return result
        receipt_guard = await self.request(
            "POST", "rpc/agent_runtime_effect_receipt_guard_readiness", body={},
        )
        if not isinstance(receipt_guard, dict) or not isinstance(receipt_guard.get("ready"), bool):
            raise AgentRuntimePersistenceError("runtime effect receipt guard readiness response is invalid")
        result["effect_receipt_guard"] = receipt_guard
        if receipt_guard["ready"] is not True:
            result["ready"] = False
            missing_guard_functions = receipt_guard.get("missing_functions") or []
            if missing_guard_functions:
                result.setdefault("missing_functions", []).extend(missing_guard_functions)
            result["missing_triggers"] = receipt_guard.get("missing_triggers") or [
                "agent_runtime_task_success_receipt_guard"
            ]
        return result

    async def list_runnable_planned_tasks(self, *, limit: int = 10) -> list[dict[str, Any]]:
        """Return due planned/native-orchestration tasks and lease-expired executions."""
        bounded_limit = max(1, min(limit, 25))
        task_kind_filter = "or(input_payload->>_runtime_plan_version.eq.1,input_payload->>_native_orchestration_version.eq.1,input_payload->>_agent_social_reply_version.eq.1)"
        now = datetime.now(timezone.utc).isoformat()
        due = await self.request("GET", "agent_runtime_tasks", params={
            "select": "*", "state": "in.(created,queued,retrying)",
            "and": f"(or(next_attempt_at.is.null,next_attempt_at.lte.{now}),{task_kind_filter})",
            "order": "created_at.asc", "limit": str(bounded_limit),
        }) or []
        expired = await self.request("GET", "agent_runtime_tasks", params={
            "select": "*", "state": "eq.executing", "lease_expires_at": f"lte.{now}",
            "or": f"(input_payload->>_runtime_plan_version.eq.1,input_payload->>_native_orchestration_version.eq.1,input_payload->>_agent_social_reply_version.eq.1)",
            "order": "created_at.asc", "limit": str(bounded_limit),
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
                                  error_code: str, lease_token: str | None = None) -> dict[str, Any] | None:
        rows = await self.request("POST", "rpc/fail_unclaimed_agent_runtime_task", body={
            "p_task_id": task_id, "p_owner_user_id": owner_id,
            "p_task_version": task_version, "p_error_code": error_code,
            "p_lease_token": lease_token,
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
