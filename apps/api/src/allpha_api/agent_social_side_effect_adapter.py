"""Real provider adapter for owner-approved Allpha Social side effects.

Execution is one canonical Postgres transaction: current runtime lease + approved
runtime policy + owner approval + Social mutation + durable effect receipt. The
adapter never treats a client/model assertion as authorization.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from allpha_api.content_api import _server_db
from allpha_api.side_effect_adapter_contract import (
    SideEffectAdapterContractError,
    SideEffectCommand,
    SideEffectOutcome,
    validate_side_effect_command,
    validate_side_effect_outcome,
)

SOCIAL_PROVIDER_KEY = "allpha.social"
SOCIAL_ACTION_KEYS = frozenset({"social.post_submit", "social.comment", "social.reply", "social.repost", "social.story_reply"})


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class AllphaSocialApprovalAdapter:
    """Executes only an owner-approved Social action via the canonical RPC."""

    provider_key = SOCIAL_PROVIDER_KEY
    supported_actions = SOCIAL_ACTION_KEYS

    def _validate_target(self, command: SideEffectCommand) -> None:
        validate_side_effect_command(command)
        if command.action_key not in self.supported_actions:
            raise SideEffectAdapterContractError("Allpha Social adapter does not support this action")
        if command.actor_user_id != command.owner_user_id:
            raise SideEffectAdapterContractError("Social approval actor must be the authenticated Agent owner")
        if command.idempotency_key != command.approval_id:
            raise SideEffectAdapterContractError("Social effect idempotency key must equal the immutable approval id")

    def _rpc_payload(self, command: SideEffectCommand) -> dict[str, Any]:
        self._validate_target(command)
        return {
            "p_task_id": command.task_id,
            "p_owner_user_id": command.owner_user_id,
            "p_lease_token": command.lease_token,
            "p_task_version": command.task_version,
            "p_step_key": command.step_key,
            "p_idempotency_key": command.idempotency_key,
            "p_input_fingerprint": command.input_fingerprint,
            "p_actor_user_id": command.actor_user_id,
            "p_agent_id": command.agent_id,
            "p_action_key": command.action_key,
            "p_target_reference": command.target_reference,
            "p_approval_id": command.approval_id,
            "p_correlation_id": command.correlation_id,
            "p_policy_id": command.policy_id,
            "p_policy_version": command.policy_version,
            "p_policy_digest": command.policy_digest,
            "p_reason": str(command.payload.get("reason") or "")[:500],
        }

    def _outcome(self, row: dict[str, Any], *, replayed: bool = False) -> SideEffectOutcome:
        if row.get("status") != "completed":
            outcome = SideEffectOutcome(
                provider_key=self.provider_key,
                status="unknown",
                result_payload={"receipt_status": row.get("status"), "replayed": replayed},
            )
            validate_side_effect_outcome(outcome, expected_provider_key=self.provider_key)
            return outcome
        completed_at = _timestamp(row.get("completed_at"))
        result = row.get("result_payload")
        if not isinstance(result, dict) or completed_at is None:
            raise SideEffectAdapterContractError("completed Social receipt is missing result or completion timestamp")
        outcome = SideEffectOutcome(
            provider_key=self.provider_key,
            status="completed",
            result_payload={**result, "receipt_id": row.get("id"), "replayed": replayed},
            external_reference=row.get("external_reference"),
            evidence_reference=row.get("evidence_reference"),
            completed_at=completed_at,
        )
        validate_side_effect_outcome(outcome, expected_provider_key=self.provider_key)
        return outcome

    async def execute(self, command: SideEffectCommand) -> SideEffectOutcome:
        rpc_name = (
            "execute_agent_social_message_approval_effect"
            if command.target_reference.startswith("conversation:")
            else "execute_agent_social_approval_effect"
        )
        result = await _server_db(
            "POST", "rpc/" + rpc_name,
            body=self._rpc_payload(command),
        )
        if not isinstance(result, dict) or result.get("outcome") not in {"completed", "replayed"}:
            raise SideEffectAdapterContractError("canonical Social effect RPC did not confirm execution")
        receipt = result.get("receipt")
        if not isinstance(receipt, dict):
            raise SideEffectAdapterContractError("canonical Social effect RPC did not return a durable receipt")
        return self._outcome(receipt, replayed=result.get("outcome") == "replayed")

    async def reconcile(
        self, command: SideEffectCommand, receipt: dict[str, Any]
    ) -> SideEffectOutcome | None:
        self._validate_target(command)
        rows = await _server_db("GET", "agent_runtime_effect_receipts", params={
            "select": "id,task_id,task_version,step_key,idempotency_key,input_fingerprint,status,result_payload,completed_at,external_reference,evidence_reference,actor_user_id,owner_user_id,agent_id,target_reference,action_key,approval_id,correlation_id,provider_key,policy_id,policy_version,policy_digest",
            "task_id": "eq." + command.task_id,
            "step_key": "eq." + command.step_key,
            "idempotency_key": "eq." + command.idempotency_key,
            "limit": "1",
        })
        if not rows:
            return None
        row = rows[0]
        expected = {
            "input_fingerprint": command.input_fingerprint,
            "actor_user_id": command.actor_user_id,
            "owner_user_id": command.owner_user_id,
            "agent_id": command.agent_id,
            "target_reference": command.target_reference,
            "action_key": command.action_key,
            "approval_id": command.approval_id,
            "correlation_id": command.correlation_id,
            "provider_key": self.provider_key,
            "policy_id": command.policy_id,
            "policy_version": command.policy_version,
            "policy_digest": command.policy_digest,
        }
        # A reclaim increments the task's fencing version. A completed receipt
        # from an earlier lease generation is valid for reconciliation as long as
        # it belongs to this same task/effect identity and is not from the future.
        stored_task_version = row.get("task_version")
        if (not isinstance(stored_task_version, int) or isinstance(stored_task_version, bool)
                or stored_task_version < 1 or stored_task_version > command.task_version):
            raise SideEffectAdapterContractError("stored Social receipt has an invalid task generation")
        if any(str(row.get(key)) != str(value) for key, value in expected.items()):
            raise SideEffectAdapterContractError("stored Social receipt does not match the requested effect identity")
        return self._outcome(row, replayed=True)


ALLPHA_SOCIAL_APPROVAL_ADAPTER = AllphaSocialApprovalAdapter()

SIDE_EFFECT_ADAPTERS = {
    SOCIAL_PROVIDER_KEY: ALLPHA_SOCIAL_APPROVAL_ADAPTER,
}


def get_side_effect_adapter(provider_key: str) -> AllphaSocialApprovalAdapter:
    adapter = SIDE_EFFECT_ADAPTERS.get(provider_key)
    if adapter is None:
        raise SideEffectAdapterContractError("No real adapter is registered for the requested provider")
    return adapter
