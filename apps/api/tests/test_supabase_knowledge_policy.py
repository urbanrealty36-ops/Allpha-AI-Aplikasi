import asyncio
import json

import httpx
import pytest

from allpha_api.knowledge_policy import KnowledgePolicyUnavailable
from allpha_api.supabase_knowledge_policy import SupabaseKnowledgePolicySnapshotProvider, build_provider

OWNER = "11111111-1111-4111-8111-111111111111"
AGENT = "22222222-2222-4222-8222-222222222222"
SOURCE = "33333333-3333-4333-8333-333333333333"


def policy_payload(**overrides):
    result = {
        "policy_version": "knowledge-policy.v1", "owner_id": OWNER, "agent_id": AGENT,
        "allowed_sensitivities": ["internal", "confidential"], "allowed_source_ids": [SOURCE],
        "audience": "owner_private", "grant_version": "grant.v1", "decision_reference": "decision-123",
        "knowledge_consent_granted": True, "consent_version": "consent.v1",
        "consent_expires_at": None, "consent_revoked": False, "grant_expires_at": None,
        "allowed_purposes": ["knowledge_ingestion", "agent_context_retrieval"], "grants_active": True,
        "resolved_at_version": "snapshot-123", "tenant_id": None, "session_id": None,
    }
    result.update(overrides)
    return result


def test_provider_posts_trusted_scope_and_returns_typed_snapshot():
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json=policy_payload())
    provider = SupabaseKnowledgePolicySnapshotProvider(
        supabase_url="https://project.supabase.co", service_role_key="server-only-test-key",
        transport=httpx.MockTransport(handler),
    )
    async def scenario():
        snapshot = await provider.resolve(
            owner_id=OWNER, agent_id=AGENT, audience="owner_private",
            tenant_id=None, session_id=None, purpose="knowledge_ingestion",
        )
        assert snapshot is not None and snapshot.owner_id == OWNER and snapshot.agent_id == AGENT
        assert snapshot.allowed_source_ids == (SOURCE,)
        assert snapshot.allowed_purposes == ("knowledge_ingestion", "agent_context_retrieval")
        assert len(calls) == 1
        assert calls[0].url.path == "/rest/v1/rpc/resolve_agent_knowledge_policy"
        assert calls[0].headers["authorization"] == "Bearer server-only-test-key"
        assert json.loads(calls[0].content) == {
            "p_owner_id": OWNER, "p_agent_id": AGENT, "p_audience": "owner_private",
            "p_tenant_id": None, "p_session_id": None, "p_purpose": "knowledge_ingestion",
        }
    asyncio.run(scenario())


@pytest.mark.parametrize("payload", [
    policy_payload(owner_id="44444444-4444-4444-8444-444444444444"),
    policy_payload(agent_id="55555555-5555-4555-8555-555555555555"),
    policy_payload(audience="tenant_shared"),
    policy_payload(allowed_source_ids="not-an-array"),
    policy_payload(allowed_sensitivities=["internal", 7]),
    policy_payload(allowed_purposes=None),
    policy_payload(knowledge_consent_granted="true"),
    policy_payload(consent_revoked=0),
    policy_payload(consent_expires_at="2026-11-24T12:00:00"),
    policy_payload(grant_expires_at=42),
])
def test_provider_rejects_malformed_or_cross_scope_receipts(payload):
    async def handler(_request):
        return httpx.Response(200, json=payload)
    provider = SupabaseKnowledgePolicySnapshotProvider(
        supabase_url="https://project.supabase.co", service_role_key="server-only-test-key",
        transport=httpx.MockTransport(handler),
    )
    async def scenario():
        with pytest.raises(KnowledgePolicyUnavailable):
            await provider.resolve(
                owner_id=OWNER, agent_id=AGENT, audience="owner_private",
                tenant_id=None, session_id=None, purpose="knowledge_ingestion",
            )
    asyncio.run(scenario())


def test_provider_rejects_duplicate_json_keys():
    async def handler(_request):
        return httpx.Response(
            200, content=b'{"policy_version":"one","policy_version":"two"}',
            headers={"content-type": "application/json"},
        )
    provider = SupabaseKnowledgePolicySnapshotProvider(
        supabase_url="https://project.supabase.co", service_role_key="server-only-test-key",
        transport=httpx.MockTransport(handler),
    )
    async def scenario():
        with pytest.raises(KnowledgePolicyUnavailable):
            await provider.resolve(
                owner_id=OWNER, agent_id=AGENT, audience="owner_private",
                tenant_id=None, session_id=None, purpose="knowledge_ingestion",
            )
    asyncio.run(scenario())


def test_provider_fails_closed_on_missing_rpc():
    async def handler(_request):
        return httpx.Response(404, json={"message": "function not found"})
    provider = SupabaseKnowledgePolicySnapshotProvider(
        supabase_url="https://project.supabase.co", service_role_key="server-only-test-key",
        transport=httpx.MockTransport(handler),
    )
    async def scenario():
        with pytest.raises(KnowledgePolicyUnavailable):
            await provider.resolve(
                owner_id=OWNER, agent_id=AGENT, audience="owner_private",
                tenant_id=None, session_id=None, purpose="knowledge_ingestion",
            )
    asyncio.run(scenario())


def test_provider_factory_requires_server_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(KnowledgePolicyUnavailable):
        build_provider()


def test_provider_preserves_timezone_aware_expiry_timestamps():
    async def handler(_request):
        return httpx.Response(200, json=policy_payload(
            consent_expires_at="2026-12-01T10:00:00+07:00",
            grant_expires_at="2026-12-02T10:00:00Z",
        ))
    provider = SupabaseKnowledgePolicySnapshotProvider(
        supabase_url="https://project.supabase.co", service_role_key="server-only-test-key",
        transport=httpx.MockTransport(handler),
    )
    async def scenario():
        snapshot = await provider.resolve(
            owner_id=OWNER, agent_id=AGENT, audience="owner_private",
            tenant_id=None, session_id=None, purpose="knowledge_ingestion",
        )
        assert snapshot.consent_expires_at == "2026-12-01T10:00:00+07:00"
        assert snapshot.grant_expires_at == "2026-12-02T10:00:00+00:00"
    asyncio.run(scenario())

def test_provider_factory_accepts_supabase_secret_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "canonical-secret-key")

    provider = build_provider()

    assert provider._service_role_key == "canonical-secret-key"
