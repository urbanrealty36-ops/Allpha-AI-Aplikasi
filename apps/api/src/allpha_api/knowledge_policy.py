"""Versioned, fail-closed knowledge access policy contract.

The resolver consumes a snapshot from an explicitly configured canonical policy
provider. It deliberately does not infer knowledge consent from general ToS/privacy
consent, nor invent a database schema. No provider is configured by default.
"""
from __future__ import annotations

import importlib
import os
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

SENSITIVITIES = frozenset({"public", "internal", "confidential", "restricted"})
RETRIEVAL_PURPOSE = "agent_context_retrieval"
KNOWLEDGE_AUDIENCES = frozenset({"owner_private", "tenant_shared", "published_knowledge", "session_scoped"})


class KnowledgePolicyUnavailable(RuntimeError):
    """Canonical policy facts are missing, invalid, or cannot be verified."""


class KnowledgePolicyDenied(KnowledgePolicyUnavailable):
    """A verified current policy explicitly denies Knowledge retrieval."""


@dataclass(frozen=True)
class KnowledgePolicySnapshot:
    policy_version: str
    owner_id: str
    agent_id: str
    allowed_sensitivities: tuple[str, ...]
    allowed_source_ids: tuple[str, ...]
    audience: str
    grant_version: str
    decision_reference: str
    knowledge_consent_granted: bool
    consent_version: str
    consent_revoked: bool
    allowed_purposes: tuple[str, ...]
    grants_active: bool
    resolved_at_version: str
    tenant_id: str | None = None
    session_id: str | None = None


class KnowledgePolicySnapshotProvider(Protocol):
    async def resolve(
        self, *, owner_id: str, agent_id: str, audience: str,
        tenant_id: str | None, session_id: str | None,
    ) -> KnowledgePolicySnapshot | None:
        """Resolve authoritative, current policy/consent/grant facts from canonical storage."""
        ...


@dataclass(frozen=True)
class ResolvedKnowledgePolicy:
    policy_version: str
    consent_version: str
    allowed_sensitivities: tuple[str, ...]
    allowed_source_ids: tuple[str, ...]
    audience: str
    grant_version: str
    decision_reference: str
    tenant_id: str | None = None
    session_id: str | None = None
    purpose: str = RETRIEVAL_PURPOSE


class VersionedKnowledgePolicyResolver:
    """Validate policy facts before retrieval; absence or ambiguity denies access."""

    def __init__(self, provider: KnowledgePolicySnapshotProvider):
        self._provider = provider

    async def resolve(
        self, *, owner_id: str, agent_id: str, audience: str = "owner_private",
        tenant_id: str | None = None, session_id: str | None = None,
    ) -> ResolvedKnowledgePolicy:
        if not isinstance(audience, str) or audience not in KNOWLEDGE_AUDIENCES:
            raise KnowledgePolicyUnavailable("knowledge retrieval audience is invalid")

        def canonical_scope_id(value: str | None, label: str) -> str | None:
            if value is None:
                return None
            if not isinstance(value, str):
                raise KnowledgePolicyUnavailable(f"trusted {label} scope is invalid")
            try:
                canonical = str(uuid.UUID(value))
            except (ValueError, TypeError, AttributeError) as exc:
                raise KnowledgePolicyUnavailable(f"trusted {label} scope is invalid") from exc
            if canonical != value.lower():
                raise KnowledgePolicyUnavailable(f"trusted {label} scope is not canonical")
            return canonical

        tenant_id = canonical_scope_id(tenant_id, "tenant")
        session_id = canonical_scope_id(session_id, "session")
        if audience == "tenant_shared" and (tenant_id is None or session_id is not None):
            raise KnowledgePolicyUnavailable("tenant_shared retrieval requires only a trusted tenant scope")
        if audience == "session_scoped" and session_id is None:
            raise KnowledgePolicyUnavailable("session_scoped retrieval requires a trusted session scope")
        if audience in {"owner_private", "published_knowledge"} and (tenant_id is not None or session_id is not None):
            raise KnowledgePolicyUnavailable("owner/published retrieval cannot carry tenant or session scope")
        try:
            snapshot = await self._provider.resolve(
                owner_id=owner_id, agent_id=agent_id, audience=audience,
                tenant_id=tenant_id, session_id=session_id,
            )
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
            or not isinstance(snapshot.audience, str) or not snapshot.audience.strip()
            or not isinstance(snapshot.grant_version, str) or not snapshot.grant_version.strip()
            or not isinstance(snapshot.decision_reference, str) or not snapshot.decision_reference.strip()
            or not isinstance(snapshot.owner_id, str)
            or snapshot.owner_id != owner_id
            or not isinstance(snapshot.agent_id, str)
            or snapshot.agent_id != agent_id
            or snapshot.tenant_id != tenant_id
            or snapshot.session_id != session_id
        ):
            raise KnowledgePolicyUnavailable("knowledge policy identity/version is invalid")
        if snapshot.audience not in KNOWLEDGE_AUDIENCES:
            raise KnowledgePolicyUnavailable("knowledge policy audience is invalid")
        if snapshot.audience != audience:
            raise KnowledgePolicyDenied("knowledge grant does not authorize this retrieval audience")
        if (
            type(snapshot.knowledge_consent_granted) is not bool
            or type(snapshot.consent_revoked) is not bool
            or type(snapshot.grants_active) is not bool
        ):
            raise KnowledgePolicyUnavailable("knowledge consent or grant state is invalid")
        if not snapshot.knowledge_consent_granted or snapshot.consent_revoked or not snapshot.grants_active:
            raise KnowledgePolicyDenied("knowledge consent or access grant is not active")
        if (
            not isinstance(snapshot.allowed_purposes, (tuple, list))
            or any(not isinstance(value, str) for value in snapshot.allowed_purposes)
            or RETRIEVAL_PURPOSE not in snapshot.allowed_purposes
        ):
            raise KnowledgePolicyUnavailable("retrieval purpose is not permitted by policy")
        if (
            not isinstance(snapshot.allowed_source_ids, (tuple, list))
            or not snapshot.allowed_source_ids
            or len(snapshot.allowed_source_ids) > 500
            or any(not isinstance(value, str) or not value.strip() for value in snapshot.allowed_source_ids)
        ):
            raise KnowledgePolicyUnavailable("knowledge source grant scope is missing or invalid")
        source_ids: list[str] = []
        for value in snapshot.allowed_source_ids:
            try:
                canonical_source_id = str(uuid.UUID(value))
            except (ValueError, TypeError, AttributeError) as exc:
                raise KnowledgePolicyUnavailable("knowledge source grant scope contains an invalid source ID") from exc
            if canonical_source_id != value.lower():
                raise KnowledgePolicyUnavailable("knowledge source grant scope contains a non-canonical source ID")
            source_ids.append(canonical_source_id)
        source_ids = list(dict.fromkeys(source_ids))
        if not source_ids:
            raise KnowledgePolicyUnavailable("knowledge source grant scope is empty")
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
            allowed_source_ids=tuple(source_ids),
            audience=snapshot.audience,
            grant_version=snapshot.grant_version,
            decision_reference=snapshot.decision_reference,
            tenant_id=tenant_id,
            session_id=session_id,
        )


class VersionedKnowledgeRetrievalPolicy:
    """Adapter that returns immutable request-local policy snapshots.

    Never cache the last resolved policy on this shared object: concurrent retrievals
    must not observe another request's consent or grant version.
    """

    def __init__(self, resolver: VersionedKnowledgePolicyResolver, *, audience: str = "owner_private"):
        self._resolver = resolver
        self._audience = audience

    async def resolve_context(
        self, *, owner_id: str, agent_id: str, audience: str | None = None,
        tenant_id: str | None = None, session_id: str | None = None,
    ) -> ResolvedKnowledgePolicy:
        try:
            return await self._resolver.resolve(
                owner_id=owner_id, agent_id=agent_id,
                audience=self._audience if audience is None else audience,
                tenant_id=tenant_id, session_id=session_id,
            )
        except KnowledgePolicyDenied as exc:
            from allpha_api.knowledge_retrieval import KnowledgeAccessDenied
            raise KnowledgeAccessDenied("knowledge consent or access grant is not active") from exc
        except KnowledgePolicyUnavailable as exc:
            from allpha_api.knowledge_retrieval import KnowledgeRetrievalUnavailable
            raise KnowledgeRetrievalUnavailable("knowledge policy is unavailable or revoked") from exc

    async def allowed_sensitivities(self, *, owner_id: str, agent_id: str) -> list[str]:
        resolved = await self.resolve_context(owner_id=owner_id, agent_id=agent_id)
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
    except Exception:
        # Configuration/import/factory failures must leave retrieval unavailable,
        # not crash startup or accidentally enable a partial policy provider.
        return None
    if not callable(getattr(provider, "resolve", None)):
        return None
    return VersionedKnowledgePolicyResolver(provider)
