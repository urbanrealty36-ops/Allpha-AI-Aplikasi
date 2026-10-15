import asyncio

import pytest

from allpha_api.knowledge_policy import (
    KnowledgePolicySnapshot,
    KnowledgePolicyUnavailable,
    VersionedKnowledgePolicyResolver,
)


def snapshot(**overrides):
    values = dict(
        policy_version="knowledge-policy.v3",
        owner_id="owner-a",
        agent_id="agent-a",
        allowed_sensitivities=("internal", "confidential"),
        knowledge_consent_granted=True,
        consent_version="knowledge-consent.v2",
        consent_revoked=False,
        allowed_purposes=("agent_context_retrieval",),
        grants_active=True,
        resolved_at_version="snapshot-42",
    )
    values.update(overrides)
    return KnowledgePolicySnapshot(**values)


class Provider:
    def __init__(self, value):
        self.value = value
        self.calls = []

    async def resolve(self, *, owner_id, agent_id):
        self.calls.append((owner_id, agent_id))
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
        assert provider.calls == [("owner-a", "agent-a")]
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
        async def resolve(self, *, owner_id, agent_id):
            raise TimeoutError("synthetic test timeout")

    async def scenario():
        with pytest.raises(KnowledgePolicyUnavailable):
            await VersionedKnowledgePolicyResolver(BrokenProvider()).resolve(
                owner_id="owner-a", agent_id="agent-a"
            )
    asyncio.run(scenario())
