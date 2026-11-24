"""Canonical Supabase RPC adapter for Knowledge consent and source grants.

The database function is the sole authority for consent, grant, owner/Agent,
source, tenant/session, audience, purpose, sensitivity, expiry and revocation.
This adapter never infers authorization from generic account consent or client
claims. It remains fail-closed while the canonical RPC is absent or unavailable.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from urllib.parse import urlsplit

import httpx

from allpha_api.knowledge_policy import KnowledgePolicySnapshot, KnowledgePolicyUnavailable

_POLICY_RPC = "resolve_agent_knowledge_policy"
_MAX_POLICY_RESPONSE_BYTES = 64 * 1024
_REQUIRED_FIELDS = frozenset({
    "policy_version", "owner_id", "agent_id", "allowed_sensitivities",
    "allowed_source_ids", "audience", "grant_version", "decision_reference",
    "knowledge_consent_granted", "consent_version", "consent_revoked",
    "allowed_purposes", "grants_active", "resolved_at_version", "tenant_id", "session_id",
})


def _expiry_value(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise KnowledgePolicyUnavailable(f"canonical Knowledge policy {label} expiry is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise KnowledgePolicyUnavailable(f"canonical Knowledge policy {label} expiry is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise KnowledgePolicyUnavailable(f"canonical Knowledge policy {label} expiry must include a timezone")
    return parsed.isoformat()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate policy response key")
        result[key] = value
    return result


def _canonical_uuid(value: str | None, label: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise KnowledgePolicyUnavailable(f"trusted {label} identity is invalid")
    try:
        canonical = str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise KnowledgePolicyUnavailable(f"trusted {label} identity is invalid") from exc
    if canonical != value.lower():
        raise KnowledgePolicyUnavailable(f"trusted {label} identity is not canonical")
    return canonical


class SupabaseKnowledgePolicySnapshotProvider:
    """Resolve a request-scoped policy snapshot through a service-only Postgres RPC."""

    def __init__(self, *, supabase_url: str, service_role_key: str,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        try:
            parsed = urlsplit(supabase_url.strip())
            host = parsed.hostname
        except ValueError as exc:
            raise KnowledgePolicyUnavailable("canonical Supabase URL is malformed") from exc
        if (parsed.scheme != "https" or not host or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or not service_role_key.strip()):
            raise KnowledgePolicyUnavailable("canonical Supabase URL and server credential are required")
        self._rpc_url = supabase_url.rstrip("/") + f"/rest/v1/rpc/{_POLICY_RPC}"
        self._service_role_key = service_role_key.strip()
        self._transport = transport

    async def resolve(self, *, owner_id: str, agent_id: str, audience: str,
                      tenant_id: str | None, session_id: str | None,
                      purpose: str) -> KnowledgePolicySnapshot | None:
        owner = _canonical_uuid(owner_id, "owner")
        agent = _canonical_uuid(agent_id, "Agent")
        tenant = _canonical_uuid(tenant_id, "tenant", optional=True)
        session = _canonical_uuid(session_id, "session", optional=True)
        if not isinstance(audience, str) or not audience.strip() or not isinstance(purpose, str) or not purpose.strip():
            raise KnowledgePolicyUnavailable("Knowledge audience and purpose are required")
        payload = {
            "p_owner_id": owner, "p_agent_id": agent, "p_audience": audience,
            "p_tenant_id": tenant, "p_session_id": session, "p_purpose": purpose,
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(6.0, connect=2.0), follow_redirects=False,
                trust_env=False, transport=self._transport,
            ) as client:
                response = await client.post(
                    self._rpc_url,
                    headers={
                        "apikey": self._service_role_key,
                        "Authorization": "Bearer " + self._service_role_key,
                        "Content-Type": "application/json", "Accept": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise KnowledgePolicyUnavailable("canonical Knowledge policy RPC is unavailable") from exc
        if len(response.content) > _MAX_POLICY_RESPONSE_BYTES:
            raise KnowledgePolicyUnavailable("canonical Knowledge policy response exceeds the size limit")
        try:
            result = json.loads(response.content.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except (ValueError, UnicodeDecodeError, RecursionError) as exc:
            raise KnowledgePolicyUnavailable("canonical Knowledge policy RPC returned invalid JSON") from exc
        if isinstance(result, list):
            result = result[0] if len(result) == 1 else None
        if not isinstance(result, dict) or set(result) != _REQUIRED_FIELDS:
            raise KnowledgePolicyUnavailable("canonical Knowledge policy RPC returned an incomplete or ambiguous snapshot")
        string_fields = (
            "policy_version", "owner_id", "agent_id", "audience", "grant_version",
            "decision_reference", "consent_version", "resolved_at_version",
        )
        if any(not isinstance(result.get(field), str) or not result[field].strip() for field in string_fields):
            raise KnowledgePolicyUnavailable("canonical Knowledge policy RPC returned invalid identity/version fields")
        if (result["owner_id"] != owner or result["agent_id"] != agent
                or result["tenant_id"] != tenant or result["session_id"] != session
                or result["audience"] != audience):
            raise KnowledgePolicyUnavailable("canonical Knowledge policy RPC returned a cross-scope snapshot")
        for field in ("allowed_sensitivities", "allowed_source_ids", "allowed_purposes"):
            value = result.get(field)
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise KnowledgePolicyUnavailable(f"canonical Knowledge policy RPC returned invalid {field}")
        consent_expires_at = _expiry_value(result.get("consent_expires_at"), "consent")
        grant_expires_at = _expiry_value(result.get("grant_expires_at"), "source-grant")
        for field in ("knowledge_consent_granted", "consent_revoked", "grants_active"):
            if type(result.get(field)) is not bool:
                raise KnowledgePolicyUnavailable(f"canonical Knowledge policy RPC returned invalid {field}")
        return KnowledgePolicySnapshot(
            policy_version=result["policy_version"], owner_id=result["owner_id"],
            agent_id=result["agent_id"], allowed_sensitivities=tuple(result["allowed_sensitivities"]),
            allowed_source_ids=tuple(result["allowed_source_ids"]), audience=result["audience"],
            grant_version=result["grant_version"], decision_reference=result["decision_reference"],
            knowledge_consent_granted=result["knowledge_consent_granted"],
            consent_version=result["consent_version"], consent_expires_at=consent_expires_at,
            consent_revoked=result["consent_revoked"], grant_expires_at=grant_expires_at,
            allowed_purposes=tuple(result["allowed_purposes"]), grants_active=result["grants_active"],
            resolved_at_version=result["resolved_at_version"], tenant_id=result["tenant_id"],
            session_id=result["session_id"],
        )


def build_provider() -> SupabaseKnowledgePolicySnapshotProvider:
    """Entry point for ALLPHA_KNOWLEDGE_POLICY_FACTORY."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not service_role_key:
        raise KnowledgePolicyUnavailable("server-side Supabase credentials are not configured")
    return SupabaseKnowledgePolicySnapshotProvider(
        supabase_url=supabase_url, service_role_key=service_role_key,
    )
