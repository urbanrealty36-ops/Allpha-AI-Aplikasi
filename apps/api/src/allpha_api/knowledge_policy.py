"""Versioned, fail-closed knowledge access policy contract.

The resolver consumes a snapshot from an explicitly configured canonical policy
provider. It deliberately does not infer knowledge consent from general ToS/privacy
consent, nor invent a database schema. No provider is configured by default.
"""
from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Callable, Protocol

SENSITIVITIES = frozenset({"public", "internal", "confidential", "restricted"})
RETRIEVAL_PURPOSE = "agent_context_retrieval"


class KnowledgePolicyUnavailable(RuntimeError):
    """Canonical policy facts are missing, invalid, stale, or revoked."""


@dataclass(frozen=True)
class KnowledgePolicySnapshot:
    policy_version: str
    owner_id: str
    agent_id: str
    allowed_sensitivities: tuple[str, ...]
    knowledge_consent_granted: bool
    consent_version: str
    consent_revoked: bool
    allowed_purposes: tuple[str, ...]
    grants_active: bool
    resolved_at_version: str


class KnowledgePolicySnapshotProvider(Protocol):
    async def resolve(self, *, owner_id: str, agent_id: str) -> KnowledgePolicySnapshot | None:
        """Resolve authoritative, current policy/consent/grant facts from canonical storage."""
        ...


@dataclass(frozen=True)
class ResolvedKnowledgePolicy:
    policy_version: str
    consent_version: str
    allowed_sensitivities: tuple[str, ...]
    purpose: str = RETRIEVAL_PURPOSE


class VersionedKnowledgePolicyResolver:
    """Validate policy facts before retrieval; absence or ambiguity denies access."""

    def __init__(self, provider: KnowledgePolicySnapshotProvider):
        self._provider = provider

    async def resolve(self, *, owner_id: str, agent_id: str) -> ResolvedKnowledgePolicy:
        try:
            snapshot = await self._provider.resolve(owner_id=owner_id, agent_id=agent_id)
        except Exception as exc:
            raise KnowledgePolicyUnavailable("canonical knowledge policy provider failed") from exc
        if snapshot is None:
            raise KnowledgePolicyUnavailable("canonical knowledge policy snapshot is unavailable")
        # Provider output crosses a trust boundary. Validate its runtime shape rather
        # than assuming type hints guarantee the configured adapter's behavior.
        if not isinstance(snapshot, KnowledgePolicySnapshot):
            raise KnowledgePolicyUnavailable("canonical knowledge policy snapshot has an invalid type")
        if (
            not isinstance(snapshot.policy_version, str)
            or not snapshot.policy_version.strip()
            or not isinstance(snapshot.consent_version, str)
            or not snapshot.consent_version.strip()
            or not isinstance(snapshot.resolved_at_version, str)
            or not snapshot.resolved_at_version.strip()
            or not isinstance(snapshot.owner_id, str)
            or snapshot.owner_id != owner_id
            or not isinstance(snapshot.agent_id, str)
            or snapshot.agent_id != agent_id
        ):
            raise KnowledgePolicyUnavailable("knowledge policy identity/version is invalid")
        if (
            type(snapshot.knowledge_consent_granted) is not bool
            or type(snapshot.consent_revoked) is not bool
            or type(snapshot.grants_active) is not bool
        ):
            raise KnowledgePolicyUnavailable("knowledge consent or grant state is invalid")
        if not snapshot.knowledge_consent_granted or snapshot.consent_revoked or not snapshot.grants_active:
            raise KnowledgePolicyUnavailable("knowledge consent or access grant is not active")
        if (
            not isinstance(snapshot.allowed_purposes, (tuple, list))
            or any(not isinstance(value, str) for value in snapshot.allowed_purposes)
            or RETRIEVAL_PURPOSE not in snapshot.allowed_purposes
        ):
            raise KnowledgePolicyUnavailable("retrieval purpose is not permitted by policy")
        if (
            not isinstance(snapshot.allowed_sensitivities, (tuple, list))
            or any(not isinstance(value, str) for value in snapshot.allowed_sensitivities)
        ):
            raise KnowledgePolicyUnavailable("knowledge sensitivity policy is missing or invalid")
        sensitivities = tuple(dict.fromkeys(snapshot.allowed_sensitivities))
        if not sensitivities or any(value not in SENSITIVITIES for value in sensitivities):
            raise KnowledgePolicyUnavailable("knowledge sensitivity policy is missing or invalid")
        return ResolvedKnowledgePolicy(
            policy_version=snapshot.policy_version,
            consent_version=snapshot.consent_version,
            allowed_sensitivities=sensitivities,
        )



class VersionedKnowledgeRetrievalPolicy:
    """Adapter implementing the retrieval service's policy interface."""

    def __init__(self, resolver: VersionedKnowledgePolicyResolver):
        self._resolver = resolver
        self.last_resolved: ResolvedKnowledgePolicy | None = None

    async def allowed_sensitivities(self, *, owner_id: str, agent_id: str) -> list[str]:
        try:
            resolved = await self._resolver.resolve(owner_id=owner_id, agent_id=agent_id)
        except KnowledgePolicyUnavailable as exc:
            # Translate policy failure into the retrieval API's stable fail-closed error.
            from allpha_api.knowledge_retrieval import KnowledgeRetrievalUnavailable
            raise KnowledgeRetrievalUnavailable("knowledge policy is unavailable or revoked") from exc
        self.last_resolved = resolved
        return list(resolved.allowed_sensitivities)

def load_policy_resolver_from_environment() -> VersionedKnowledgePolicyResolver | None:
    """Load an explicitly configured server-only module:function policy provider.

    No environment allowlist is treated as an authorization policy. The provider must
    resolve current knowledge-specific consent, revocation, grant and policy version.
    """
    spec = os.getenv("ALLPHA_KNOWLEDGE_POLICY_FACTORY", "").strip()
    if not spec or ":" not in spec:
        return None
    module_name, function_name = spec.split(":", 1)
    if not module_name or not function_name:
        return None
    try:
        factory: Callable[[], KnowledgePolicySnapshotProvider] = getattr(
            importlib.import_module(module_name), function_name
        )
        provider = factory()
    except (ImportError, AttributeError, TypeError, ValueError):
        return None
    if not callable(getattr(provider, "resolve", None)):
        return None
    return VersionedKnowledgePolicyResolver(provider)
