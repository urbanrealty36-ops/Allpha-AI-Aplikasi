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


def test_worker_readiness_requires_success_receipt_guard():
    calls = []

    async def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/agent_runtime_worker_schema_readiness"):
            return httpx.Response(200, json={
                "ready": True, "missing_tables": [], "missing_columns": [],
                "missing_functions": [], "missing_privileges": [],
            })
        if request.url.path.endswith("/agent_runtime_effect_receipt_guard_readiness"):
            return httpx.Response(200, json={
                "ready": False,
                "missing_triggers": ["agent_runtime_task_success_receipt_guard"],
                "missing_functions": [],
            })
        return httpx.Response(404)

    store = AgentRuntimeStore(
        supabase_url="https://example.supabase.co",
        service_key="test-service-role-key",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(store.runtime_schema_readiness())
    assert result["ready"] is False
    assert result["missing_triggers"] == ["agent_runtime_task_success_receipt_guard"]
    assert result["missing_functions"] == []
    assert calls == [
        "/rest/v1/rpc/agent_runtime_worker_schema_readiness",
        "/rest/v1/rpc/agent_runtime_effect_receipt_guard_readiness",
    ]


def test_runtime_skill_resolution_uses_exact_immutable_published_snapshot():
    requests = []
    owner_id = "owner-1"
    agent_id = "agent-1"
    skill_id = "skill-1"
    snapshot = {
        "id": skill_id, "agent_id": agent_id, "version": 7, "status": "published",
        "tool_dependencies": ["text.normalize"], "required_permission_scopes": ["content:read"],
        "budget_limits": {"max_runtime_seconds": 15, "max_tool_calls": 2},
        "instructions": "immutable published instructions",
    }

    async def handler(request):
        requests.append(request)
        if request.url.path.endswith("/agent_ownerships"):
            return httpx.Response(200, json=[{"agent_id": agent_id}])
        if request.url.path.endswith("/agent_skill_installations"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/agent_skill_versions"):
            return httpx.Response(200, json=[{"snapshot": snapshot}])
        return httpx.Response(404)

    store = AgentRuntimeStore(
        supabase_url="https://example.supabase.co",
        service_key="test-service-role-key",
        transport=httpx.MockTransport(handler),
    )
    resolved = asyncio.run(store.get_skill(owner_id, agent_id, skill_id, version=7))

    assert resolved == snapshot
    assert [request.url.path for request in requests] == [
        "/rest/v1/agent_ownerships", "/rest/v1/agent_skill_installations", "/rest/v1/agent_skill_versions",
    ]
    assert requests[1].url.params["installed_skill_id"] == f"eq.{skill_id}"
    assert requests[2].url.params["version"] == "eq.7"
    assert requests[2].url.params["skill_id"] == f"eq.{skill_id}"


def test_runtime_skill_resolution_fails_closed_when_pinned_snapshot_is_missing():
    async def handler(request):
        if request.url.path.endswith("/agent_ownerships"):
            return httpx.Response(200, json=[{"agent_id": "agent-1"}])
        if request.url.path.endswith("/agent_skill_installations"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/agent_skill_versions"):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    store = AgentRuntimeStore(
        supabase_url="https://example.supabase.co",
        service_key="test-service-role-key",
        transport=httpx.MockTransport(handler),
    )
    resolved = asyncio.run(store.get_skill("owner-1", "agent-1", "skill-1", version=4))
    assert resolved is None


def test_runtime_skill_resolution_requires_active_unexpired_installation_license():
    requests=[]
    snapshot={"id":"skill-1","agent_id":"agent-1","version":7,"status":"published"}
    async def handler(request):
        requests.append(request)
        if request.url.path.endswith("/agent_ownerships"):
            return httpx.Response(200,json=[{"agent_id":"agent-1"}])
        if request.url.path.endswith("/agent_skill_installations"):
            return httpx.Response(200,json=[{
                "id":"installation-1","status":"active","license_terms_digest":"a"*64,
                "accepted_at":"2026-11-24T00:00:00Z","license_expires_at":None,
            }])
        if request.url.path.endswith("/agent_skill_versions"):
            return httpx.Response(200,json=[{"snapshot":snapshot}])
        return httpx.Response(404)
    store=AgentRuntimeStore(supabase_url="https://example.supabase.co",service_key="test-service-role-key",transport=httpx.MockTransport(handler))
    assert asyncio.run(store.get_skill("owner-1","agent-1","skill-1",version=7))==snapshot
    assert requests[1].url.path.endswith("/agent_skill_installations")


def test_runtime_skill_resolution_fails_closed_after_installation_revocation():
    requests=[]
    async def handler(request):
        requests.append(request)
        if request.url.path.endswith("/agent_ownerships"):
            return httpx.Response(200,json=[{"agent_id":"agent-1"}])
        if request.url.path.endswith("/agent_skill_installations"):
            return httpx.Response(200,json=[{
                "id":"installation-1","status":"revoked","license_terms_digest":"a"*64,
                "accepted_at":"2026-11-24T00:00:00Z","license_expires_at":None,
            }])
        return httpx.Response(200,json=[{"snapshot":{"id":"skill-1","agent_id":"agent-1","version":7,"status":"published"}}])
    store=AgentRuntimeStore(supabase_url="https://example.supabase.co",service_key="test-service-role-key",transport=httpx.MockTransport(handler))
    assert asyncio.run(store.get_skill("owner-1","agent-1","skill-1",version=7)) is None
    assert not any(request.url.path.endswith("/agent_skill_versions") for request in requests)


def test_runtime_skill_resolution_fails_closed_after_license_expiry():
    async def handler(request):
        if request.url.path.endswith("/agent_ownerships"):
            return httpx.Response(200,json=[{"agent_id":"agent-1"}])
        if request.url.path.endswith("/agent_skill_installations"):
            return httpx.Response(200,json=[{
                "id":"installation-1","status":"active","license_terms_digest":"a"*64,
                "accepted_at":"2026-11-24T00:00:00Z","license_expires_at":"2020-01-01T00:00:00Z",
            }])
        return httpx.Response(200,json=[{"snapshot":{"id":"skill-1","agent_id":"agent-1","version":7,"status":"published"}}])
    store=AgentRuntimeStore(supabase_url="https://example.supabase.co",service_key="test-service-role-key",transport=httpx.MockTransport(handler))
    assert asyncio.run(store.get_skill("owner-1","agent-1","skill-1",version=7)) is None
