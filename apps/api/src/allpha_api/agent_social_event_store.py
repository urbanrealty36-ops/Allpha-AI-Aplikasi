"""Durable WP-06 Social event inbox adapter.

The inbox is only an intake/claim ledger. Runtime execution and scheduling remain
owned by AgentRuntimeStore / agent_runtime_tasks; this module does not run a worker.
"""
from __future__ import annotations

import uuid
from typing import Any

from allpha_api.agent_runtime_store import AgentRuntimePersistenceError, AgentRuntimeStore


class AgentSocialEventPersistenceError(RuntimeError):
    """A durable event transition could not be confirmed."""


class AgentSocialEventStore:
    def __init__(self, runtime_store: AgentRuntimeStore) -> None:
        self._store = runtime_store

    @classmethod
    def from_environment(cls) -> "AgentSocialEventStore":
        return cls(AgentRuntimeStore.from_environment())

    async def claim(self, *, limit: int = 10, lease_seconds: int = 60,
                    claim_token: str | None = None) -> list[dict[str, Any]]:
        token = claim_token or str(uuid.uuid4())
        try:
            rows = await self._store.request("POST", "rpc/claim_agent_social_automation_events", body={
                "p_claim_token": token, "p_limit": max(1, min(limit, 50)),
                "p_lease_seconds": max(10, min(lease_seconds, 300)),
            })
        except AgentRuntimePersistenceError as exc:
            raise AgentSocialEventPersistenceError("Social event claim outcome is unknown") from exc
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise AgentSocialEventPersistenceError("Social event claim returned an invalid envelope")
        return rows

    async def heartbeat(self, event_id: str, claim_token: str, *,
                        lease_seconds: int = 60) -> dict[str, Any]:
        try:
            rows = await self._store.request("POST", "rpc/heartbeat_agent_social_automation_event", body={
                "p_event_id": event_id, "p_claim_token": claim_token,
                "p_lease_seconds": max(10, min(lease_seconds, 300)),
            })
        except AgentRuntimePersistenceError as exc:
            raise AgentSocialEventPersistenceError("Social event heartbeat outcome is unknown") from exc
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise AgentSocialEventPersistenceError("Social event lease is stale or heartbeat was not confirmed")
        return rows[0]

    async def mark_dispatched(self, event_id: str, claim_token: str,
                              runtime_task_id: str) -> dict[str, Any]:
        try:
            rows = await self._store.request("POST", "rpc/complete_agent_social_automation_event", body={
                "p_event_id": event_id, "p_claim_token": claim_token,
                "p_runtime_task_id": runtime_task_id,
            })
        except AgentRuntimePersistenceError as exc:
            raise AgentSocialEventPersistenceError("Social event dispatch link outcome is unknown") from exc
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise AgentSocialEventPersistenceError("Social event dispatch link was not confirmed")
        return rows[0]

    async def fail(self, event_id: str, claim_token: str, reason_code: str, *,
                   retry_after_seconds: int = 60) -> dict[str, Any]:
        try:
            rows = await self._store.request("POST", "rpc/fail_agent_social_automation_event", body={
                "p_event_id": event_id, "p_claim_token": claim_token,
                "p_reason_code": reason_code[:120],
                "p_retry_after_seconds": max(5, min(retry_after_seconds, 86400)),
            })
        except AgentRuntimePersistenceError as exc:
            raise AgentSocialEventPersistenceError("Social event retry transition outcome is unknown") from exc
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise AgentSocialEventPersistenceError("Social event retry transition was not confirmed")
        return rows[0]

    async def cancel_for_owner(self, owner_user_id: str, agent_id: str,
                               reason_code: str = "owner_takeover") -> int:
        try:
            result = await self._store.request("POST", "rpc/cancel_agent_social_automation_events", body={
                "p_owner_user_id": owner_user_id, "p_agent_id": agent_id,
                "p_reason_code": reason_code[:120],
            })
        except AgentRuntimePersistenceError as exc:
            raise AgentSocialEventPersistenceError("Social event cancellation outcome is unknown") from exc
        if isinstance(result, bool) or not isinstance(result, int) or result < 0:
            raise AgentSocialEventPersistenceError("Social event cancellation returned an invalid count")
        return result
