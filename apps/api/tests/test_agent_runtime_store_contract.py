import asyncio
import json

import httpx

from allpha_api.agent_runtime_store import AgentRuntimeStore


def test_effect_receipt_rpc_preserves_stable_idempotency_key_and_fingerprint():
    requests = []
    receipt = {
        "task_id": "task-1",
        "step_key": "tool:payments.charge",
        "idempotency_key": "charge-task-123",
        "input_fingerprint": "a" * 64,
        "status": "started",
    }

    async def handler(request):
        requests.append(request)
        if request.url.path.endswith("/begin_agent_runtime_effect"):
            return httpx.Response(200, json=[receipt])
        completed = {**receipt, "status": "completed", "result_payload": {"receipt": "provider-1"}}
        return httpx.Response(200, json=[completed])

    store = AgentRuntimeStore(
        supabase_url="https://example.supabase.co",
        service_key="test-service-role-key",
        transport=httpx.MockTransport(handler),
    )

    async def exercise():
        started = await store.begin_effect(
            "owner-1", "task-1", "lease-1", 7, "tool:payments.charge",
            "charge-task-123", "a" * 64,
        )
        completed = await store.complete_effect(
            "owner-1", "task-1", "lease-1", 7, "tool:payments.charge",
            "charge-task-123", "a" * 64, {"receipt": "provider-1"},
        )
        return started, completed

    started, completed = asyncio.run(exercise())
    assert started["status"] == "started"
    assert completed["status"] == "completed"
    assert len(requests) == 2
    begin_body = json.loads(requests[0].content)
    complete_body = json.loads(requests[1].content)
    assert begin_body["p_idempotency_key"] == complete_body["p_idempotency_key"] == "charge-task-123"
    assert begin_body["p_input_fingerprint"] == complete_body["p_input_fingerprint"] == "a" * 64
    assert requests[0].url.path.endswith("/rpc/begin_agent_runtime_effect")
    assert requests[1].url.path.endswith("/rpc/complete_agent_runtime_effect")
