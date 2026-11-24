import asyncio
from types import SimpleNamespace

import pytest

from allpha_api.knowledge_policy import (
    KnowledgePolicyDenied,
    KnowledgePolicySnapshot,
    KnowledgePolicyUnavailable,
    VersionedKnowledgePolicyResolver,
    load_policy_resolver_from_environment,
)


def snapshot(**overrides):
    values = dict(
        policy_version="knowledge-policy.v3",
        owner_id="owner-a",
        agent_id="agent-a",
        allowed_sensitivities=("internal", "confidential"),
        allowed_source_ids=("00000000-0000-0000-0000-0000000000c9",),
        audience="owner_private", grant_version="knowledge-grant.v1",
        decision_reference="decision-42",
        knowledge_consent_granted=True,
        consent_version="knowledge-consent.v2",
        consent_revoked=False,
        allowed_purposes=("agent_context_retrieval",),
        grants_active=True,
        resolved_at_version="snapshot-42",
        tenant_id=None,
        session_id=None,
    )
    values.update(overrides)
    return KnowledgePolicySnapshot(**values)


class Provider:
    def __init__(self, value):
        self.value = value
        self.calls = []

    async def resolve(self, *, owner_id, agent_id, audience, tenant_id, session_id, purpose):
        self.calls.append((owner_id, agent_id, audience, tenant_id, session_id, purpose))
        return self.value


def test_versioned_policy_resolves_current_owner_agent_consent_and_sensitivities():
    async def scenario():
        provider = Provider(snapshot())
        resolved = await VersionedKnowledgePolicyResolver(provider).resolve(
            owner_id="owner-a", agent_id="agent-a"
        )
        assert resolved.policy_version == "knowledge-policy.v3"
        assert resolved.consent_version == "knowledge-consent.v2"
        assert resolved.allowed_sensitivities == ("internal", "confidential")
        assert resolved.allowed_source_ids == ("00000000-0000-0000-0000-0000000000c9",)
        assert resolved.grant_version == "knowledge-grant.v1"
        assert resolved.audience == "owner_private"
        assert provider.calls == [("owner-a", "agent-a", "owner_private", None, None, "agent_context_retrieval")]
    asyncio.run(scenario())


@pytest.mark.parametrize("overrides", [
    {"owner_id": "owner-b"},
    {"agent_id": "agent-b"},
    {"policy_version": ""},
    {"consent_version": ""},
    {"resolved_at_version": ""},
    {"knowledge_consent_granted": False},
    {"consent_revoked": True},
    {"grants_active": False},
    {"allowed_purposes": ("analytics",)},
    {"allowed_sensitivities": ()},
    {"allowed_sensitivities": ("internal", "unknown")},
    {"allowed_source_ids": ()},
    {"allowed_source_ids": ("not-a-uuid",)},
    {"audience": ""},
    {"grant_version": ""},
    {"decision_reference": ""},
])
def test_versioned_policy_fails_closed_for_invalid_or_revoked_facts(overrides):
    async def scenario():
        with pytest.raises(KnowledgePolicyUnavailable):
            await VersionedKnowledgePolicyResolver(Provider(snapshot(**overrides))).resolve(
                owner_id="owner-a", agent_id="agent-a"
            )
    asyncio.run(scenario())


def test_versioned_policy_fails_closed_when_snapshot_is_missing():
    async def scenario():
        with pytest.raises(KnowledgePolicyUnavailable):
            await VersionedKnowledgePolicyResolver(Provider(None)).resolve(
                owner_id="owner-a", agent_id="agent-a"
            )
    asyncio.run(scenario())


def test_versioned_policy_fails_closed_when_provider_raises():
    class BrokenProvider:
        async def resolve(self, *, owner_id, agent_id, audience, tenant_id, session_id, purpose):
            raise TimeoutError("synthetic test timeout")

    async def scenario():
        with pytest.raises(KnowledgePolicyUnavailable):
            await VersionedKnowledgePolicyResolver(BrokenProvider()).resolve(
                owner_id="owner-a", agent_id="agent-a"
            )
    asyncio.run(scenario())


@pytest.mark.parametrize("value", [
    {},
    "not-a-policy-snapshot",
    snapshot(policy_version=None),
    snapshot(consent_version=42),
    snapshot(resolved_at_version=None),
    snapshot(knowledge_consent_granted="true"),
    snapshot(consent_revoked=0),
    snapshot(grants_active=None),
    snapshot(allowed_purposes=None),
    snapshot(allowed_purposes=("agent_context_retrieval", 7)),
    snapshot(allowed_sensitivities=None),
    snapshot(allowed_sensitivities=("internal", None)),
])
def test_versioned_policy_fails_closed_on_malformed_provider_snapshot(value):
    async def scenario():
        with pytest.raises(KnowledgePolicyUnavailable):
            await VersionedKnowledgePolicyResolver(Provider(value)).resolve(
                owner_id="owner-a", agent_id="agent-a"
            )
    asyncio.run(scenario())


def test_policy_factory_returns_none_when_module_import_fails(monkeypatch):
    monkeypatch.setenv("ALLPHA_KNOWLEDGE_POLICY_FACTORY", "missing_module:build_provider")

    def fail_import(_module_name):
        raise RuntimeError("synthetic import-time configuration failure")

    monkeypatch.setattr("allpha_api.knowledge_policy.importlib.import_module", fail_import)
    assert load_policy_resolver_from_environment() is None


def test_policy_factory_returns_none_when_provider_factory_raises(monkeypatch):
    monkeypatch.setenv("ALLPHA_KNOWLEDGE_POLICY_FACTORY", "policy_module:build_provider")

    def fail_factory():
        raise RuntimeError("synthetic provider factory failure")

    monkeypatch.setattr(
        "allpha_api.knowledge_policy.importlib.import_module",
        lambda _module_name: SimpleNamespace(build_provider=fail_factory),
    )
    assert load_policy_resolver_from_environment() is None


def test_policy_factory_returns_none_when_provider_has_no_resolve_method(monkeypatch):
    monkeypatch.setenv("ALLPHA_KNOWLEDGE_POLICY_FACTORY", "policy_module:build_provider")
    monkeypatch.setattr(
        "allpha_api.knowledge_policy.importlib.import_module",
        lambda _module_name: SimpleNamespace(build_provider=lambda: object()),
    )
    assert load_policy_resolver_from_environment() is None



def test_verified_knowledge_consent_revocation_is_a_distinct_policy_denial():
    async def scenario():
        resolver = VersionedKnowledgePolicyResolver(Provider(snapshot(consent_revoked=True)))
        with pytest.raises(KnowledgePolicyDenied):
            await resolver.resolve(owner_id="owner-a", agent_id="agent-a")

    asyncio.run(scenario())


def test_retrieval_policy_maps_verified_consent_denial_to_access_denied():
    from allpha_api.knowledge_retrieval import KnowledgeAccessDenied
    from allpha_api.knowledge_policy import VersionedKnowledgeRetrievalPolicy

    async def scenario():
        resolver = VersionedKnowledgePolicyResolver(Provider(snapshot(grants_active=False)))
        policy = VersionedKnowledgeRetrievalPolicy(resolver)
        with pytest.raises(KnowledgeAccessDenied):
            await policy.allowed_sensitivities(owner_id="owner-a", agent_id="agent-a")

    asyncio.run(scenario())



def test_versioned_retrieval_policy_returns_request_local_context_without_shared_cache():
    from allpha_api.knowledge_policy import VersionedKnowledgeRetrievalPolicy

    async def scenario():
        policy = VersionedKnowledgeRetrievalPolicy(
            VersionedKnowledgePolicyResolver(Provider(snapshot()))
        )
        first = await policy.resolve_context(owner_id="owner-a", agent_id="agent-a")
        second = await policy.resolve_context(owner_id="owner-a", agent_id="agent-a")
        assert first.policy_version == "knowledge-policy.v3"
        assert second.consent_version == "knowledge-consent.v2"
        assert not hasattr(policy, "last_resolved")

    asyncio.run(scenario())


def test_versioned_policy_rejects_audience_mismatch_before_allowing_retrieval():
    async def scenario():
        resolver = VersionedKnowledgePolicyResolver(Provider(snapshot(audience="owner_private")))
        with pytest.raises(KnowledgePolicyDenied):
            await resolver.resolve(owner_id="owner-a", agent_id="agent-a", audience="published_knowledge")
    asyncio.run(scenario())


def test_versioned_policy_supports_explicit_published_knowledge_audience():
    async def scenario():
        resolver = VersionedKnowledgePolicyResolver(Provider(snapshot(audience="published_knowledge")))
        resolved = await resolver.resolve(
            owner_id="owner-a", agent_id="agent-a", audience="published_knowledge"
        )
        assert resolved.audience == "published_knowledge"
    asyncio.run(scenario())


def test_versioned_policy_rejects_unknown_audience():
    async def scenario():
        provider = Provider(snapshot())
        with pytest.raises(KnowledgePolicyUnavailable):
            await VersionedKnowledgePolicyResolver(provider).resolve(
                owner_id="owner-a", agent_id="agent-a", audience="public_catalog"
            )
        assert provider.calls == []
    asyncio.run(scenario())


def test_tenant_shared_policy_requires_and_binds_trusted_tenant_scope():
    async def scenario():
        tenant_id = "00000000-0000-0000-0000-0000000000aa"
        provider = Provider(snapshot(audience="tenant_shared", tenant_id=tenant_id))
        resolver = VersionedKnowledgePolicyResolver(provider)
        with pytest.raises(KnowledgePolicyUnavailable):
            await resolver.resolve(owner_id="owner-a", agent_id="agent-a", audience="tenant_shared")
        resolved = await resolver.resolve(
            owner_id="owner-a", agent_id="agent-a", audience="tenant_shared", tenant_id=tenant_id
        )
        assert resolved.tenant_id == tenant_id
        assert resolved.session_id is None
        assert provider.calls[-1] == ("owner-a", "agent-a", "tenant_shared", tenant_id, None, "agent_context_retrieval")
    asyncio.run(scenario())


def test_tenant_shared_policy_rejects_cross_tenant_snapshot():
    async def scenario():
        provider = Provider(snapshot(
            audience="tenant_shared",
            tenant_id="00000000-0000-0000-0000-0000000000bb",
        ))
        with pytest.raises(KnowledgePolicyUnavailable):
            await VersionedKnowledgePolicyResolver(provider).resolve(
                owner_id="owner-a", agent_id="agent-a", audience="tenant_shared",
                tenant_id="00000000-0000-0000-0000-0000000000aa",
            )
    asyncio.run(scenario())


def test_session_scoped_policy_requires_and_binds_trusted_session_scope():
    async def scenario():
        session_id = "00000000-0000-0000-0000-0000000000cc"
        provider = Provider(snapshot(audience="session_scoped", session_id=session_id))
        resolver = VersionedKnowledgePolicyResolver(provider)
        with pytest.raises(KnowledgePolicyUnavailable):
            await resolver.resolve(owner_id="owner-a", agent_id="agent-a", audience="session_scoped")
        resolved = await resolver.resolve(
            owner_id="owner-a", agent_id="agent-a", audience="session_scoped", session_id=session_id
        )
        assert resolved.session_id == session_id
    asyncio.run(scenario())


def test_scoped_audiences_reject_noncanonical_scope_ids_before_provider_lookup():
    async def scenario():
        provider = Provider(snapshot())
        with pytest.raises(KnowledgePolicyUnavailable):
            await VersionedKnowledgePolicyResolver(provider).resolve(
                owner_id="owner-a", agent_id="agent-a", audience="tenant_shared", tenant_id="not-a-uuid"
            )
        assert provider.calls == []
    asyncio.run(scenario())


def test_owner_private_policy_rejects_caller_supplied_tenant_or_session_scope():
    async def scenario():
        provider = Provider(snapshot())
        with pytest.raises(KnowledgePolicyUnavailable):
            await VersionedKnowledgePolicyResolver(provider).resolve(
                owner_id="owner-a", agent_id="agent-a",
                tenant_id="00000000-0000-0000-0000-0000000000aa",
            )
        assert provider.calls == []
    asyncio.run(scenario())


def test_policy_provider_receives_exact_requested_purpose_and_enforces_it():
    async def scenario():
        provider = Provider(snapshot(allowed_purposes=("agent_context_retrieval", "knowledge_summarization")))
        resolver = VersionedKnowledgePolicyResolver(provider)
        resolved = await resolver.resolve(
            owner_id="owner-a", agent_id="agent-a", purpose="knowledge_summarization"
        )
        assert resolved.purpose == "knowledge_summarization"
        assert provider.calls[-1][-1] == "knowledge_summarization"
        with pytest.raises(KnowledgePolicyUnavailable):
            await resolver.resolve(
                owner_id="owner-a", agent_id="agent-a", purpose="knowledge_export"
            )
    asyncio.run(scenario())


@pytest.mark.parametrize("purpose", ["", " " * 129, None])
def test_policy_rejects_invalid_purpose_before_provider_lookup(purpose):
    async def scenario():
        provider = Provider(snapshot())
        with pytest.raises(KnowledgePolicyUnavailable):
            await VersionedKnowledgePolicyResolver(provider).resolve(
                owner_id="owner-a", agent_id="agent-a", purpose=purpose
            )
        assert provider.calls == []
    asyncio.run(scenario())


def test_source_authorization_requires_exact_source_sensitivity_and_purpose():
    async def scenario():
        resolver = VersionedKnowledgePolicyResolver(Provider(snapshot()))
        allowed = await resolver.authorize_source(owner_id="owner-a", agent_id="agent-a", source_id="00000000-0000-0000-0000-0000000000c9", sensitivity="internal", purpose="knowledge_ingestion")
        assert allowed.purpose == "knowledge_ingestion"
        with pytest.raises(KnowledgePolicyDenied):
            await resolver.authorize_source(owner_id="owner-a", agent_id="agent-a", source_id="00000000-0000-0000-0000-0000000000c8", sensitivity="internal", purpose="knowledge_ingestion")
        with pytest.raises(KnowledgePolicyDenied):
            await resolver.authorize_source(owner_id="owner-a", agent_id="agent-a", source_id="00000000-0000-0000-0000-0000000000c9", sensitivity="restricted", purpose="knowledge_ingestion")
    asyncio.run(scenario())
