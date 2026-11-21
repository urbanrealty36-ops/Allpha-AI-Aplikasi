"""WP-06 durable Social event consumer and canonical Agent Runtime execution.

This module consumes the WP-06 inbox but never owns a second queue/runtime. All
execution tasks, leases, checkpoints and terminal transitions stay in
AgentRuntimeStore; model calls go through AgentRuntime + the canonical Model Router.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone, time as clock_time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException

from allpha_api.agent_runtime import AgentRuntime, AgentRuntimeBlocked, AgentRuntimeOutcomeUnknown
from allpha_api.agent_runtime_store import AgentRuntimePersistenceError, AgentRuntimeStore
from allpha_api.credit_ledger_contract import CreditReservationCommand
from allpha_api.credit_ledger_service import (
    ApprovedLifecyclePolicy, CreditLifecycleBlocked, CreditLedgerLifecycleService,
    OperationOutcome,
)
from allpha_api.generation_output_moderation import load_generation_output_moderator
from allpha_api.memory_coordinator import MemoryCoordinator, MemoryDenied, MemoryUnavailable
from allpha_api.model_router import TextGenerationRequest, TextGenerationRouterUnavailable
from allpha_api.supabase_credit_ledger_store import SupabaseCreditLedgerStore
from allpha_api.text_generation_adapters import build_text_generation_router_from_environment

logger = logging.getLogger("allpha.agent_social_automation")
SOCIAL_TASK_MARKER = "_agent_social_reply_version"
SOCIAL_TASK_VERSION = 1
_ACTION_BY_CHANNEL = {"comments": ("social.reply", "draft_reply"),
                      "mentions": ("social.comment", "draft_comment"),
                      "dm": ("social.reply", "draft_reply")}
_LEASE_SECONDS = 90


class AgentSocialEventBlocked(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class AgentSocialEventDeferred(AgentSocialEventBlocked):
    def __init__(self, reason_code: str, retry_after_seconds: int) -> None:
        super().__init__(reason_code)
        self.retry_after_seconds = max(5, min(retry_after_seconds, 86400))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def is_agent_social_reply_task(row: dict[str, Any]) -> bool:
    payload = row.get("input_payload")
    return isinstance(payload, dict) and payload.get(SOCIAL_TASK_MARKER) == SOCIAL_TASK_VERSION


async def _rows(store: AgentRuntimeStore, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    rows = await store.request("GET", table, params=params)
    if not isinstance(rows, list):
        raise AgentRuntimePersistenceError(f"WP-06 {table} projection is invalid")
    return [row for row in rows if isinstance(row, dict)]


async def _one(store: AgentRuntimeStore, table: str, params: dict[str, str]) -> dict[str, Any] | None:
    rows = await _rows(store, table, {**params, "limit": "1"})
    return rows[0] if rows else None


async def _event_heartbeat(
    store: AgentRuntimeStore,
    event_id: str,
    claim_token: str,
    stop: asyncio.Event,
    lease_lost: asyncio.Event,
    *,
    interval_seconds: float = 15,
) -> None:
    """Renew an event lease; an uncertain heartbeat must stop dispatch fail-closed."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            return
        except asyncio.TimeoutError:
            try:
                rows = await store.request("POST", "rpc/heartbeat_agent_social_automation_event", body={
                    "p_event_id": event_id, "p_claim_token": claim_token, "p_lease_seconds": 90,
                })
            except asyncio.CancelledError:
                raise
            except Exception:
                lease_lost.set()
                logger.exception("WP-06 event lease heartbeat failed; dispatch must stop")
                return
            if not rows:
                lease_lost.set()
                return


async def _block_event(store: AgentRuntimeStore, event: dict[str, Any], claim_token: str,
                       reason_code: str) -> None:
    rows = await store.request("POST", "rpc/block_agent_social_automation_event", body={
        "p_event_id": str(event["id"]), "p_claim_token": claim_token,
        "p_reason_code": reason_code[:120],
    })
    if not rows:
        raise AgentRuntimePersistenceError("WP-06 event block transition was not confirmed")


async def _fail_event(store: AgentRuntimeStore, event: dict[str, Any], claim_token: str,
                      reason_code: str, retry_after: int = 60) -> None:
    rows = await store.request("POST", "rpc/fail_agent_social_automation_event", body={
        "p_event_id": str(event["id"]), "p_claim_token": claim_token,
        "p_reason_code": reason_code[:120], "p_retry_after_seconds": max(5, min(retry_after, 86400)),
    })
    if not rows:
        raise AgentRuntimePersistenceError("WP-06 event retry transition was not confirmed")


def _is_quiet(policy: dict[str, Any]) -> bool:
    quiet = policy.get("quiet_hours") or {}
    if not quiet:
        return False
    if not isinstance(quiet, dict) or set(quiet) - {"timezone", "start", "end"}:
        raise AgentSocialEventBlocked("SOCIAL_QUIET_HOURS_POLICY_UNSUPPORTED")
    zone_name, start, end = quiet.get("timezone"), quiet.get("start"), quiet.get("end")
    if not isinstance(zone_name, str) or not isinstance(start, str) or not isinstance(end, str):
        raise AgentSocialEventBlocked("SOCIAL_QUIET_HOURS_POLICY_INVALID")
    try:
        zone = ZoneInfo(zone_name)
        start_time, end_time = clock_time.fromisoformat(start), clock_time.fromisoformat(end)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise AgentSocialEventBlocked("SOCIAL_QUIET_HOURS_POLICY_INVALID") from exc
    local_now = datetime.now(timezone.utc).astimezone(zone).time().replace(tzinfo=None)
    if start_time == end_time:
        raise AgentSocialEventBlocked("SOCIAL_QUIET_HOURS_POLICY_INVALID")
    return (start_time <= local_now < end_time if start_time < end_time
            else local_now >= start_time or local_now < end_time)


async def _load_credit_terms(store: AgentRuntimeStore, action_tool: str,
                             route_snapshot: dict[str, Any]) -> dict[str, Any]:
    capability_id = os.getenv("ALLPHA_AGENT_SOCIAL_CREDIT_CAPABILITY_ID", "").strip()
    entitlement_version = os.getenv("ALLPHA_AGENT_SOCIAL_CREDIT_ENTITLEMENT_VERSION", "").strip()
    if not capability_id or not entitlement_version:
        raise AgentSocialEventBlocked("APPROVED_SOCIAL_CREDIT_CAPABILITY_AND_ENTITLEMENT_NOT_CONFIGURED")
    rows = await _rows(store, "credit_policy_versions", {
        "select": "policy_version,credit_scheme_version,approval_reference,status,configuration,effective_at,expires_at",
        "status": "eq.approved", "order": "effective_at.desc.nullslast,created_at.desc", "limit": "20",
    })
    now = datetime.now(timezone.utc)
    for row in rows:
        try:
            effective = datetime.fromisoformat(str(row["effective_at"]).replace("Z", "+00:00")) if row.get("effective_at") else None
            expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00")) if row.get("expires_at") else None
        except (TypeError, ValueError):
            continue
        if effective and effective > now or expires and expires <= now:
            continue
        configuration = row.get("configuration")
        if not isinstance(configuration, dict):
            continue
        cap = (configuration.get("capabilities") or {}).get(capability_id)
        entitlement = (configuration.get("entitlements") or {}).get(entitlement_version)
        lifecycle = configuration.get("lifecycle")
        if not isinstance(cap, dict) or not isinstance(entitlement, dict) or not isinstance(lifecycle, dict):
            continue
        required_cap = ("tariff_version", "usage_unit", "credits_per_usage_unit",
                        "cost_unit", "cost_pricing_version", "max_cost_microunits",
                        "max_usage_units_per_request")
        if any(key not in cap for key in required_cap) or cap.get("action_tool_key") != action_tool:
            continue
        try:
            units = int(cap["max_usage_units_per_request"])
            rate = int(cap["credits_per_usage_unit"])
            maximum_cost = int(cap["max_cost_microunits"])
            max_request = int(entitlement["max_credits_per_request"])
            max_concurrent = int(entitlement["max_concurrent_reservations"])
        except (TypeError, ValueError):
            continue
        if (route_snapshot.get("pricing_version") != cap.get("cost_pricing_version")
                or route_snapshot.get("cost_unit") != cap.get("cost_unit")
                or maximum_cost > int(route_snapshot.get("max_cost_microunits") or 0)):
            continue
        if min(units, rate, maximum_cost, max_request, max_concurrent) <= 0:
            continue
        credits = units * rate
        if credits > max_request:
            continue
        if not lifecycle.get("allow_success_settlement") or not lifecycle.get("allow_definitive_failure_release"):
            continue
        if lifecycle.get("allow_unknown_outcome_release") is True:
            continue
        return {
            "policy_version": str(row["policy_version"]),
            "credit_scheme_version": str(row["credit_scheme_version"]),
            "approval_reference": str(row["approval_reference"]),
            "capability_id": capability_id,
            "tariff_version": str(cap["tariff_version"]),
            "usage_unit": str(cap["usage_unit"]),
            "credits_per_usage_unit": rate,
            "estimated_usage_units": units,
            "credits_to_reserve": credits,
            "cost_unit": str(cap["cost_unit"]),
            "estimated_cost_microunits": maximum_cost,
            "entitlement_version": entitlement_version,
            "lifecycle": lifecycle,
            "configuration_digest": _sha(configuration),
        }
    raise AgentSocialEventBlocked("APPROVED_SOCIAL_CREDIT_POLICY_OR_MATCHING_TARIFF_NOT_FOUND")


async def _load_social_snapshot(store: AgentRuntimeStore, event: dict[str, Any],
                                router: Any) -> dict[str, Any]:
    owner_id, agent_id = str(event["owner_user_id"]), str(event["agent_id"])
    channel = str(event.get("channel") or "")
    if channel not in {"comments", "mentions", "dm", "live_chat"}:
        raise AgentSocialEventBlocked("SOCIAL_EVENT_CHANNEL_INVALID")
    if channel == "live_chat":
        raise AgentSocialEventBlocked("ENG_P25_LIVE_AGENT_PARTICIPANT_AUTHORITY_NOT_AVAILABLE")
    if (channel == "dm"
            and os.getenv("ALLPHA_AGENT_SOCIAL_DM_APPROVAL_SCHEMA_ENABLED", "false").lower() != "true"):
        raise AgentSocialEventBlocked("WP06_DM_APPROVAL_SCHEMA_NOT_ACTIVE")
    actor_id = str(event.get("source_actor_user_id") or "")
    if not actor_id or actor_id == owner_id:
        raise AgentSocialEventBlocked("SOCIAL_EVENT_ACTOR_INVALID")

    agent = await store.get_agent(owner_id, agent_id)
    if not agent or agent.get("status") != "active":
        raise AgentSocialEventBlocked("SOCIAL_AGENT_NOT_ACTIVE")
    policies = await _rows(store, "agent_social_presence_policies", {
        "select": "*", "owner_user_id": "eq." + owner_id, "agent_id": "eq." + agent_id,
    })
    policy = policies[0] if policies else None
    if (not policy or not policy.get("is_enabled") or policy.get("revoked_at")
            or not policy.get("auto_reply_enabled") or policy.get("takeover_active")
            or channel not in (policy.get("auto_reply_channels") or [])
            or policy.get("owner_approval_required") is not True
            or policy.get("output_moderation_required") is not True):
        raise AgentSocialEventBlocked("SOCIAL_OWNER_POLICY_NOT_AUTHORIZED")
    if _is_quiet(policy):
        raise AgentSocialEventDeferred("SOCIAL_QUIET_HOURS_ACTIVE", 900)

    grants = await _rows(store, "agent_social_automation_grants", {
        "select": "*", "owner_user_id": "eq." + owner_id, "agent_id": "eq." + agent_id,
        "status": "eq.active", "policy_version": "eq." + str(policy.get("version")),
        "order": "granted_at.desc", "limit": "20",
    })
    now = datetime.now(timezone.utc)
    grant = None
    for candidate in grants:
        if channel not in (candidate.get("granted_scopes") or []):
            continue
        expires = candidate.get("expires_at")
        if expires:
            try:
                if datetime.fromisoformat(str(expires).replace("Z", "+00:00")) <= now:
                    continue
            except ValueError:
                continue
        grant = candidate
        break
    if not grant:
        raise AgentSocialEventBlocked("SOCIAL_OWNER_GRANT_NOT_ACTIVE")

    skill_id = str(policy.get("auto_reply_skill_id") or "")
    if not skill_id:
        raise AgentSocialEventBlocked("SOCIAL_AUTO_REPLY_SKILL_NOT_CONFIGURED")
    skill = await store.get_skill(owner_id, agent_id, skill_id)
    if not skill or skill.get("status") != "published":
        raise AgentSocialEventBlocked("SOCIAL_PUBLISHED_SKILL_NOT_FOUND")
    action_tool, action_type = _ACTION_BY_CHANNEL[channel]
    dependencies = skill.get("tool_dependencies") or []
    if dependencies != [action_tool]:
        raise AgentSocialEventBlocked("SOCIAL_SKILL_MUST_PIN_ONLY_THE_APPROVED_REPLY_ACTION_TOOL")
    if action_type not in (policy.get("allowed_actions") or []):
        raise AgentSocialEventBlocked("SOCIAL_OWNER_ACTION_POLICY_NOT_AUTHORIZED")
    allowed_scopes = set(policy.get("allowed_tool_scopes") or [])
    skill_scopes = set(skill.get("required_permission_scopes") or [])
    if not skill_scopes.issubset(allowed_scopes):
        raise AgentSocialEventBlocked("SOCIAL_SKILL_PERMISSION_SCOPE_NOT_GRANTED")
    capability = await store.get_approved_capability(agent_id, action_tool)
    if not capability or not capability.get("runtime_policy_id"):
        raise AgentSocialEventBlocked("SOCIAL_ACTION_CAPABILITY_NOT_APPROVED")
    runtime_policy = await store.get_approved_runtime_policy(agent_id, str(capability["runtime_policy_id"]))
    if not runtime_policy or runtime_policy.get("policy_version") != capability.get("policy_version"):
        raise AgentSocialEventBlocked("SOCIAL_ACTION_RUNTIME_POLICY_NOT_APPROVED")
    policy_document = runtime_policy.get("policy_document")
    if not isinstance(policy_document, dict) or _sha(policy_document) != runtime_policy.get("policy_digest"):
        raise AgentSocialEventBlocked("SOCIAL_ACTION_RUNTIME_POLICY_DIGEST_INVALID")
    policy_scopes = set(runtime_policy.get("required_permission_scopes") or [])
    capability_scopes = set(capability.get("required_permission_scopes") or [])
    if (action_tool not in (runtime_policy.get("approved_tool_keys") or [])
            or not policy_scopes.issubset(allowed_scopes)
            or not capability_scopes.issubset(policy_scopes)):
        raise AgentSocialEventBlocked("SOCIAL_ACTION_RUNTIME_PERMISSION_NOT_GRANTED")

    source = await _one(store, str(event["source_table"]), {
        "select": "*", "id": "eq." + str(event["source_record_id"]),
    })
    if not source:
        raise AgentSocialEventBlocked("SOCIAL_EVENT_SOURCE_NOT_FOUND")
    conversation_history: list[dict[str, str]] = []
    target_conversation_id: str | None = None
    target_message_id: str | None = None
    recipient_user_id: str | None = None
    if channel == "dm":
        target_conversation_id = str(event.get("conversation_id") or source.get("conversation_id") or "")
        target_message_id = str(source.get("id") or "")
        if (str(event.get("source_table")) != "messages"
                or not target_conversation_id or target_message_id != str(event.get("source_record_id"))
                or str(source.get("conversation_id")) != target_conversation_id
                or source.get("sender_type") != "human"
                or str(source.get("sender_user_id")) != actor_id):
            raise AgentSocialEventBlocked("SOCIAL_DM_SOURCE_MESSAGE_ACL_FAILED")
        conversations = await _rows(store, "conversations", {
            "select": "id,kind", "id": "eq." + target_conversation_id, "limit": "1",
        })
        if not conversations or conversations[0].get("kind") != "agent":
            raise AgentSocialEventBlocked("SOCIAL_DM_CONVERSATION_KIND_INVALID")
        participants = await _rows(store, "conversation_participants", {
            "select": "user_id,agent_id,participant_type,joined_at",
            "conversation_id": "eq." + target_conversation_id,
        })
        humans = [p for p in participants if p.get("participant_type") == "human" and p.get("joined_at")]
        agents = [p for p in participants if p.get("participant_type") == "agent" and p.get("joined_at")]
        if (len(participants) != 2 or len(humans) != 1 or len(agents) != 1
                or str(humans[0].get("user_id")) != actor_id
                or str(agents[0].get("agent_id")) != agent_id):
            raise AgentSocialEventBlocked("SOCIAL_DM_PARTICIPANT_ACL_FAILED")
        recipient_user_id = actor_id
        latest_human = await _rows(store, "messages", {
            "select": "id", "conversation_id": "eq." + target_conversation_id,
            "sender_type": "eq.human", "order": "created_at.desc,id.desc", "limit": "1",
        })
        if not latest_human or str(latest_human[0].get("id")) != target_message_id:
            raise AgentSocialEventBlocked("SOCIAL_DM_SOURCE_MESSAGE_STALE")
        history_rows = await _rows(store, "messages", {
            "select": "id,sender_type,sender_user_id,sender_agent_id,body,created_at",
            "conversation_id": "eq." + target_conversation_id,
            "order": "created_at.desc", "limit": "12",
        })
        for item in reversed(history_rows):
            if item.get("sender_type") == "human" and str(item.get("sender_user_id")) == actor_id:
                role = "human"
            elif item.get("sender_type") == "agent" and str(item.get("sender_agent_id")) == agent_id:
                role = "agent"
            else:
                raise AgentSocialEventBlocked("SOCIAL_DM_HISTORY_PARTICIPANT_ACL_FAILED")
            body = str(item.get("body") or "")
            if not body or len(body) > 10000:
                raise AgentSocialEventBlocked("SOCIAL_DM_HISTORY_CONTENT_INVALID")
            conversation_history.append({"role": role, "body": body})
        if not any(item.get("id") == target_message_id for item in history_rows):
            raise AgentSocialEventBlocked("SOCIAL_DM_SOURCE_MESSAGE_NOT_IN_CONTEXT")
        content_id = ""
        content = None
    else:
        if channel == "comments":
            if str(source.get("actor_user_id")) != actor_id or source.get("status") != "visible":
                raise AgentSocialEventBlocked("SOCIAL_COMMENT_SOURCE_ACL_FAILED")
        else:
            if str(source.get("mentioner_user_id")) != actor_id:
                raise AgentSocialEventBlocked("SOCIAL_MENTION_SOURCE_ACL_FAILED")
        content_id = str(event.get("content_id") or source.get("content_id") or "")
        content = await _one(store, "content_items", {
            "select": "id,owner_id,ai_agent_id,body,visibility,status,deleted_at",
            "id": "eq." + content_id,
        }) if content_id else None
        if (not content or content.get("status") != "published" or content.get("deleted_at")
                or content.get("visibility") != "public"):
            raise AgentSocialEventBlocked("SOCIAL_CONTENT_PRIVACY_OR_LIFECYCLE_DENIED")
        if channel == "comments" and str(content.get("owner_id")) != owner_id:
            raise AgentSocialEventBlocked("SOCIAL_COMMENT_CONTENT_OWNER_MISMATCH")
        if channel == "mentions" and str(event.get("owner_user_id")) != owner_id:
            raise AgentSocialEventBlocked("SOCIAL_MENTION_OWNER_MISMATCH")

    blocked = await _rows(store, "social_edges", {
        "select": "id", "edge_type": "eq.block", "status": "eq.active",
        "or": "(and(actor_user_id.eq." + owner_id + ",target_user_id.eq." + actor_id + "),and(actor_user_id.eq." + actor_id + ",target_user_id.eq." + owner_id + "))",
    })
    if blocked:
        raise AgentSocialEventBlocked("SOCIAL_BLOCK_EDGE_ACTIVE")

    since = datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat()
    recent = await _rows(store, "agent_social_automation_events", {
        "select": "id", "owner_user_id": "eq." + owner_id, "agent_id": "eq." + agent_id,
        "channel": "eq." + channel, "created_at": "gte." + since,
        "status": "not.in.(ignored,blocked,cancelled,dead_letter)", "limit": "30",
    })
    if len(recent) > int(policy.get("max_replies_per_minute") or 1):
        raise AgentSocialEventDeferred("SOCIAL_RATE_LIMIT_EXCEEDED", 60)

    source_body = str(source.get("body") or "")
    content_body = str(content.get("body") or "") if isinstance(content, dict) else ""
    if not source_body and channel == "comments":
        raise AgentSocialEventBlocked("SOCIAL_COMMENT_BODY_EMPTY")
    policy_topics = [str(item).casefold() for item in (policy.get("blocked_topics") or [])]
    combined = (source_body + "\n" + content_body + "\n" + "\n".join(item["body"] for item in conversation_history)).casefold()
    if any(topic and topic in combined for topic in policy_topics):
        raise AgentSocialEventBlocked("SOCIAL_BLOCKED_TOPIC_MATCH")
    escalation = policy.get("escalation_rules") or {}
    if not isinstance(escalation, dict) or set(escalation) - {"keywords", "require_human_review", "max_message_chars"}:
        raise AgentSocialEventBlocked("SOCIAL_ESCALATION_POLICY_INVALID")
    keywords = escalation.get("keywords") or []
    if not isinstance(keywords, list) or any(not isinstance(item, str) or not item.strip() for item in keywords):
        raise AgentSocialEventBlocked("SOCIAL_ESCALATION_POLICY_INVALID")
    if any(item.casefold() in combined for item in keywords):
        raise AgentSocialEventBlocked("SOCIAL_ESCALATION_REQUIRED")
    max_chars = escalation.get("max_message_chars", 10000)
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or not 1 <= max_chars <= 10000:
        raise AgentSocialEventBlocked("SOCIAL_ESCALATION_POLICY_INVALID")

    sensitivity = "internal"
    route_snapshot = await router.preflight(sensitivity)
    if not isinstance(route_snapshot, dict) or route_snapshot.get("status") != "ready":
        raise AgentSocialEventBlocked("SOCIAL_MODEL_ROUTER_PREFLIGHT_FAILED")
    credit_terms = await _load_credit_terms(store, action_tool, route_snapshot.get("route") or {})
    if int(policy.get("daily_credit_budget") or 0) <= 0:
        raise AgentSocialEventBlocked("SOCIAL_DAILY_CREDIT_BUDGET_NOT_CONFIGURED")
    if credit_terms["credits_to_reserve"] > int(policy["daily_credit_budget"]):
        raise AgentSocialEventBlocked("SOCIAL_REQUEST_EXCEEDS_DAILY_CREDIT_BUDGET")

    memory_context: list[dict[str, Any]] = []
    memory_refs: list[dict[str, Any]] = []
    if "memory.read:agent_runtime_context" in allowed_scopes:
        if os.getenv("ALLPHA_MEMORY_COORDINATOR_ENABLED", "false").lower() != "true":
            raise AgentSocialEventBlocked("SOCIAL_MEMORY_COORDINATOR_NOT_ACTIVATED")
        try:
            items = await MemoryCoordinator().retrieve_context(
                owner_id, agent_id, purpose="agent_runtime_context", query=source_body,
                limit=4, max_chars=1500, max_sensitivity="internal",
            )
        except (MemoryDenied, MemoryUnavailable) as exc:
            raise AgentSocialEventBlocked("SOCIAL_ACL_FILTERED_MEMORY_UNAVAILABLE") from exc
        for item in items:
            body = str(item.get("content") or "")
            if not body or hashlib.sha256(body.encode()).hexdigest() != item.get("retrieved_content_sha256"):
                raise AgentSocialEventBlocked("SOCIAL_MEMORY_PROVENANCE_INVALID")
            memory_context.append({"memory_type": item.get("memory_type"),
                                   "classification": item.get("classification"), "content": body})
            memory_refs.append({
                "id": item.get("id"), "policy_id": item.get("policy_id"),
                "policy_version": item.get("policy_version"), "memory_type": item.get("memory_type"),
                "classification": item.get("classification"), "purpose": item.get("purpose"),
                "content_sha256": item.get("content_sha256"),
                "retrieved_content_sha256": item.get("retrieved_content_sha256"),
                "source_ref": item.get("source_ref"), "provenance": item.get("provenance"),
            })
    if any(scope.startswith("knowledge.read") for scope in allowed_scopes):
        raise AgentSocialEventBlocked("SOCIAL_KNOWLEDGE_ACL_PROVIDER_NOT_CONFIGURED")

    context = {
        "channel": channel, "actor_id": actor_id, "source_table": event["source_table"],
        "source_record_id": event["source_record_id"], "content_id": content_id,
        "source_body": source_body, "content_body": content_body,
        "conversation_id": target_conversation_id, "target_message_id": target_message_id,
        "recipient_user_id": recipient_user_id, "conversation_history": conversation_history,
        "memory_context": memory_context, "memory_context_refs": memory_refs,
    }
    snapshot = {
        "agent_id": agent_id, "agent_version": int(agent.get("version") or 0),
        "skill_id": skill_id, "skill_version": int(skill.get("version") or 0),
        "skill_tool_dependencies": sorted(dependencies),
        "skill_permission_scopes": sorted(skill_scopes),
        "social_policy_id": str(policy["id"]), "social_policy_version": int(policy["version"]),
        "automation_version": int(policy.get("automation_version") or 0),
        "automation_grant_id": str(grant["id"]), "grant_policy_version": int(grant["policy_version"]),
        "grant_scopes": sorted(grant.get("granted_scopes") or []),
        "action_tool_key": action_tool, "action_type": action_type,
        "action_capability_snapshot": {
            "capability_id": str(capability["id"]), "capability_key": action_tool,
            "runtime_policy_id": str(runtime_policy["id"]),
            "policy_version": str(runtime_policy["policy_version"]),
            "policy_digest": str(runtime_policy["policy_digest"]),
            "approved_tool_keys": sorted(runtime_policy.get("approved_tool_keys") or []),
            "required_permission_scopes": sorted(policy_scopes),
            "capability_permission_scopes": sorted(capability_scopes),
        },
        "route_snapshot": route_snapshot.get("route"),
        "route_preflight": route_snapshot,
        "credit_terms": credit_terms,
        "daily_credit_budget": int(policy["daily_credit_budget"]),
        "reply_tone": str(policy.get("reply_tone") or "friendly_concise"),
        "disclosure_text": str(policy.get("disclosure_text") or "Dibuat bersama AI Agent"),
        "max_message_chars": max_chars,
        "context": context,
        "context_snapshot_sha256": _sha(context),
        "memory_context_sha256": _sha(memory_context),
        "memory_policy_versions": sorted({str(item.get("policy_version")) for item in memory_refs if item.get("policy_version") is not None}),
        "correlation_id": str(event["id"]),
        "idempotency_key": "agent-social-event:" + str(event["id"]),
    }
    snapshot["snapshot_sha256"] = _sha(snapshot)
    return snapshot


async def _session_for_event(store: AgentRuntimeStore, owner_id: str, agent_id: str,
                             event_id: str) -> str:
    sessions = await _rows(store, "agent_runtime_sessions", {
        "select": "id,owner_user_id,agent_id,status", "owner_user_id": "eq." + owner_id,
        "agent_id": "eq." + agent_id, "status": "eq.active",
        "order": "last_activity_at.desc", "limit": "20",
    })
    if sessions:
        return str(sessions[0]["id"])
    row = await store.create_session({
        "owner_user_id": owner_id, "agent_id": agent_id,
        "title": "Auto Reply Social",
        "status": "active", "metadata": {"source": "wp06_social_automation", "source_event_id": event_id},
    })
    return str(row["id"])


async def _dispatch_event(store: AgentRuntimeStore, event: dict[str, Any],
                          claim_token: str, router: Any) -> None:
    expected_fingerprint = hashlib.sha256(
        (str(event["owner_user_id"]) + ":" + str(event["agent_id"]) + ":" +
         str(event["channel"]) + ":" + str(event["source_table"]) + ":" +
         str(event["source_record_id"])).encode("utf-8")
    ).hexdigest()
    if event.get("event_fingerprint") != expected_fingerprint:
        raise AgentSocialEventBlocked("SOCIAL_EVENT_FINGERPRINT_INVALID")
    snapshot = await _load_social_snapshot(store, event, router)
    owner_id, agent_id = str(event["owner_user_id"]), str(event["agent_id"])
    session_id = await _session_for_event(store, owner_id, agent_id, str(event["id"]))
    payload = {SOCIAL_TASK_MARKER: SOCIAL_TASK_VERSION, "event_id": str(event["id"]),
               "social_snapshot": snapshot}
    fingerprint = _sha(payload)
    idempotency_key = snapshot["idempotency_key"]
    existing = await store.find_task_by_idempotency(owner_id, idempotency_key)
    if existing:
        if existing.get("request_fingerprint") != fingerprint:
            raise AgentSocialEventBlocked("SOCIAL_EVENT_RUNTIME_IDEMPOTENCY_CONFLICT")
        task = existing
    else:
        trace_id = str(event["id"])
        task = await store.create_task({
            "owner_user_id": owner_id, "session_id": session_id, "agent_id": agent_id,
            "skill_id": snapshot["skill_id"], "agent_version": snapshot["agent_version"],
            "skill_version": snapshot["skill_version"], "state": "created",
            "idempotency_key": idempotency_key, "request_fingerprint": fingerprint,
            "tool_key": "agent.social_auto_reply", "input_payload": payload,
            "task_budget_limits": {"max_runtime_seconds": 30, "max_tool_calls": 1},
            "event_log": [{"state": "created", "at": datetime.now(timezone.utc).isoformat(),
                           "trace_id": trace_id, "reason_code": "wp06_social_event_dispatch"}],
            "trace_id": trace_id,
        })
    completed = await store.request("POST", "rpc/complete_agent_social_automation_event", body={
        "p_event_id": str(event["id"]), "p_claim_token": claim_token,
        "p_runtime_task_id": str(task["id"]),
    })
    if not completed:
        # The stable task idempotency key lets the next event claim reconcile this write.
        raise AgentRuntimePersistenceError("WP-06 event-to-runtime link was not confirmed")


async def run_social_events_once(store: AgentRuntimeStore, *, limit: int = 5) -> int:
    """Claim and dispatch one bounded batch to the canonical Agent Runtime task table."""
    router = build_text_generation_router_from_environment()
    if (os.getenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "false").lower() != "true"
            or os.getenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_WORKER_ENABLED", "false").lower() != "true"
            or not callable(getattr(store, "request", None))):
        return 0
    if router is None:
        logger.warning("WP-06 event dispatch paused: canonical text-generation Model Router is not configured")
        return 0
    claim_token = str(uuid.uuid4())
    events = await store.request("POST", "rpc/claim_agent_social_automation_events", body={
        "p_claim_token": claim_token, "p_limit": max(1, min(limit, 25)), "p_lease_seconds": 90,
    })
    if not isinstance(events, list):
        raise AgentRuntimePersistenceError("WP-06 event claim returned an invalid result")
    dispatched = 0
    for event in events:
        if not isinstance(event, dict) or not event.get("id"):
            continue
        stop = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat = asyncio.create_task(
            _event_heartbeat(store, str(event["id"]), claim_token, stop, lease_lost)
        )
        try:
            await _dispatch_event(store, event, claim_token, router)
            if lease_lost.is_set():
                raise AgentRuntimePersistenceError(
                    "WP-06 event lease heartbeat was lost during dispatch; event outcome requires reconciliation"
                )
            dispatched += 1
        except AgentSocialEventDeferred as exc:
            if lease_lost.is_set():
                raise AgentRuntimePersistenceError(
                    "WP-06 event lease was lost; retry transition cannot be trusted"
                ) from exc
            await _fail_event(store, event, claim_token, exc.reason_code, exc.retry_after_seconds)
        except AgentSocialEventBlocked as exc:
            if lease_lost.is_set():
                raise AgentRuntimePersistenceError(
                    "WP-06 event lease was lost; block transition cannot be trusted"
                ) from exc
            await _block_event(store, event, claim_token, exc.reason_code)
        except AgentRuntimePersistenceError:
            logger.exception("WP-06 event persistence uncertain; stopping current batch")
            raise
        except TextGenerationRouterUnavailable as exc:
            if lease_lost.is_set():
                raise AgentRuntimePersistenceError(
                    "WP-06 event lease was lost; retry transition cannot be trusted"
                ) from exc
            await _fail_event(store, event, claim_token, "SOCIAL_MODEL_ROUTER_TEMPORARILY_UNAVAILABLE", 120)
        except Exception as exc:
            if lease_lost.is_set():
                raise AgentRuntimePersistenceError(
                    "WP-06 event lease was lost; dispatch outcome requires reconciliation"
                ) from exc
            logger.exception("WP-06 event dispatch failed; event_id=%s", event.get("id"))
            await _fail_event(store, event, claim_token, "SOCIAL_EVENT_DISPATCH_FAILED", 120)
        finally:
            stop.set()
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass
    return dispatched


async def _current_policy_and_grant(store: AgentRuntimeStore, snapshot: dict[str, Any],
                                    owner_id: str, agent_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = await _one(store, "agent_social_presence_policies", {
        "select": "*", "owner_user_id": "eq." + owner_id, "agent_id": "eq." + agent_id,
    })
    if (not policy or not policy.get("is_enabled") or policy.get("revoked_at")
            or not policy.get("auto_reply_enabled") or policy.get("takeover_active")
            or int(policy.get("version") or 0) != snapshot.get("social_policy_version")
            or int(policy.get("automation_version") or 0) != snapshot.get("automation_version")):
        raise AgentSocialEventBlocked("SOCIAL_POLICY_CHANGED_BEFORE_EXECUTION")
    grant = await _one(store, "agent_social_automation_grants", {
        "select": "*", "id": "eq." + str(snapshot["automation_grant_id"]),
        "owner_user_id": "eq." + owner_id, "agent_id": "eq." + agent_id,
        "status": "eq.active",
    })
    if not grant or int(grant.get("policy_version") or 0) != snapshot.get("grant_policy_version"):
        raise AgentSocialEventBlocked("SOCIAL_GRANT_REVOKED_BEFORE_EXECUTION")
    expires = grant.get("expires_at")
    if expires and datetime.fromisoformat(str(expires).replace("Z", "+00:00")) <= datetime.now(timezone.utc):
        raise AgentSocialEventBlocked("SOCIAL_GRANT_EXPIRED_BEFORE_EXECUTION")
    return policy, grant


async def _reserve_social_credits(store: AgentRuntimeStore, snapshot: dict[str, Any],
                                  owner_id: str, task_id: str) -> tuple[Any, CreditLedgerLifecycleService, ApprovedLifecyclePolicy]:
    terms = snapshot["credit_terms"]
    command = CreditReservationCommand(
        idempotency_key="social-credit-reserve:" + task_id,
        account_id=owner_id, task_id=task_id, capability_id=terms["capability_id"],
        credits_to_reserve=terms["credits_to_reserve"],
        credit_scheme_version=terms["credit_scheme_version"],
        tariff_version=terms["tariff_version"], entitlement_version=terms["entitlement_version"],
        policy_approval_reference=terms["approval_reference"],
        policy_version=terms["policy_version"],
        estimated_usage_units=terms["estimated_usage_units"], usage_unit=terms["usage_unit"],
        estimated_cost_microunits=terms["estimated_cost_microunits"], cost_unit=terms["cost_unit"],
    )
    ledger_store = SupabaseCreditLedgerStore.from_environment()
    lifecycle = CreditLedgerLifecycleService(ledger_store)
    approved_policy = ApprovedLifecyclePolicy(
        policy_version=terms["policy_version"], approval_reference=terms["approval_reference"],
        allow_success_settlement=bool(terms["lifecycle"].get("allow_success_settlement")),
        allow_definitive_failure_release=bool(terms["lifecycle"].get("allow_definitive_failure_release")),
        allow_partial_settlement=bool(terms["lifecycle"].get("allow_partial_settlement")),
        allow_unknown_outcome_release=False,
    )
    reservation = await ledger_store.reserve_agent_social_auto_reply(
        command, agent_id=str(snapshot["agent_id"]), daily_budget=int(snapshot["daily_credit_budget"]),
    )
    return reservation, lifecycle, approved_policy


async def _settle_social_reservation(
    store: AgentRuntimeStore, lifecycle: CreditLedgerLifecycleService, reservation: Any,
    policy: ApprovedLifecyclePolicy, *, owner_id: str, task_id: str,
    evidence_payload: dict[str, Any], actual_credits: int, actual_usage_units: int,
    usage_unit: str,
) -> None:
    state = str(getattr(reservation.state, "value", reservation.state))
    if state == "settled":
        row = await _one(store, "credit_reservations", {
            "select": "id,owner_user_id,task_id,state,settled_credits,source_event_id",
            "id": "eq." + str(reservation.reservation_id),
            "owner_user_id": "eq." + owner_id, "task_id": "eq." + task_id,
        })
        if (not row or row.get("state") != "settled"
                or int(row.get("settled_credits") or 0) != actual_credits
                or row.get("source_event_id") != evidence_payload.get("idempotency_key")):
            raise AgentRuntimePersistenceError("WP-06 settled reservation does not match persisted provider metering")
        return
    if state == "released":
        raise AgentRuntimePersistenceError("WP-06 reservation was released before successful metering reconciliation")
    await lifecycle.complete(
        reservation=reservation, outcome=OperationOutcome.SUCCEEDED, policy=policy,
        idempotency_key="social-credit-settle:" + task_id,
        source_event_id=str(evidence_payload["idempotency_key"]),
        actual_credits=actual_credits, actual_usage_units=actual_usage_units,
        usage_unit=usage_unit,
    )


async def _task_heartbeat(
    store: AgentRuntimeStore,
    owner_id: str,
    task_id: str,
    lease_token: str,
    task_version: int,
    stop: asyncio.Event,
    lease_lost: asyncio.Event,
    cancellation_requested: asyncio.Event,
    *,
    interval_seconds: float = 15,
) -> None:
    """Renew the canonical task lease and surface lease loss/cancellation fail-closed."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            return
        except asyncio.TimeoutError:
            pass
        if stop.is_set():
            return
        try:
            row = await store.heartbeat_task(
                owner_id, task_id, lease_token, task_version, lease_seconds=_LEASE_SECONDS,
            )
        except asyncio.CancelledError:
            raise
        except AgentRuntimePersistenceError:
            lease_lost.set()
            logger.exception("WP-06 Agent Runtime task heartbeat failed; execution must stop")
            return
        if not row:
            lease_lost.set()
            return
        if row.get("cancel_requested") is True:
            cancellation_requested.set()
            return


async def execute_agent_social_reply_task(store: AgentRuntimeStore, owner_id: str, task_id: str,
                                          initial_row: dict[str, Any], router: Any = None) -> dict[str, Any]:
    """Execute one social reply through AgentRuntime, canonical Model Router and AI Credit Ledger."""
    if initial_row.get("state") == "succeeded":
        return {"task": initial_row, "idempotent_replay": True}
    payload = initial_row.get("input_payload")
    snapshot = payload.get("social_snapshot") if isinstance(payload, dict) else None
    if not is_agent_social_reply_task(initial_row) or not isinstance(snapshot, dict):
        raise HTTPException(409, detail={"code": "SOCIAL_RUNTIME_PAYLOAD_INVALID"})
    router = router or build_text_generation_router_from_environment()
    if router is None:
        raise HTTPException(503, detail={"code": "SOCIAL_MODEL_ROUTER_UNAVAILABLE"})
    if _sha({key: value for key, value in snapshot.items() if key != "snapshot_sha256"}) != snapshot.get("snapshot_sha256"):
        raise HTTPException(409, detail={"code": "SOCIAL_RUNTIME_SNAPSHOT_INVALID"})

    task_version = int(initial_row.get("task_version") or 1)
    if initial_row.get("state") == "executing":
        expiry = initial_row.get("lease_expires_at")
        if expiry and datetime.fromisoformat(str(expiry).replace("Z", "+00:00")) > datetime.now(timezone.utc):
            raise HTTPException(409, detail={"code": "TASK_ALREADY_CLAIMED"})
        if initial_row.get("effect_outcome") in {"started", "unknown"}:
            await store.mark_unknown_effect(owner_id, task_id)
            raise HTTPException(409, detail={"code": "SOCIAL_PROVIDER_OUTCOME_UNKNOWN"})
    lease_token = str(uuid.uuid4())
    claimed = await store.claim_task(owner_id, task_id, lease_token, lease_seconds=_LEASE_SECONDS)
    if not claimed:
        latest = await store.get_task(owner_id, task_id)
        if latest and latest.get("state") == "succeeded":
            return {"task": latest, "idempotent_replay": True}
        raise HTTPException(409, detail={"code": "TASK_ALREADY_CLAIMED"})
    task_version = int(claimed["task_version"])
    await store.request("PATCH", "agent_social_automation_runs", params={
        "owner_user_id": "eq." + owner_id, "runtime_task_id": "eq." + task_id,
    }, body={"status": "running", "updated_at": datetime.now(timezone.utc).isoformat()})
    stop = asyncio.Event()
    lease_lost = asyncio.Event()
    cancellation_requested = asyncio.Event()
    heartbeat = asyncio.create_task(_task_heartbeat(
        store, owner_id, task_id, lease_token, task_version, stop,
        lease_lost, cancellation_requested,
    ))
    reservation = None
    lifecycle = None
    approved_policy = None
    provider_started = False

    async def refresh_cancellation_state() -> None:
        latest = await store.get_task(owner_id, task_id)
        if latest and latest.get("cancel_requested") is True:
            cancellation_requested.set()

    async def finish_cancelled(*, provider_usage: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if lease_lost.is_set():
            raise AgentRuntimePersistenceError("WP-06 task lease heartbeat was lost; cancellation cannot be committed")
        await refresh_cancellation_state()
        if not cancellation_requested.is_set() and claimed.get("cancel_requested") is not True:
            return None
        if reservation and lifecycle and approved_policy and not provider_started:
            await lifecycle.complete(
                reservation=reservation, outcome=OperationOutcome.FAILED_DEFINITIVE,
                policy=approved_policy, idempotency_key="social-credit-release:" + task_id,
                source_event_id="social-generation:" + task_id,
            )
        final = await store.finalize_task(
            owner_id, task_id, lease_token, task_version, state="cancelled",
            output_payload=({"reason_code": "cancelled_after_generation",
                             "provider_usage": provider_usage} if provider_usage else None),
            error_code="cancelled_by_requester",
            event_log=list(claimed.get("event_log") or []) + [{
                "state": "cancelled", "at": datetime.now(timezone.utc).isoformat(),
                "trace_id": snapshot.get("correlation_id"), "reason_code": "cancelled_by_requester",
            }],
        )
        if not final:
            raise AgentRuntimePersistenceError("WP-06 cancellation could not be durably committed")
        await store.request("PATCH", "agent_social_automation_runs", params={
            "owner_user_id": "eq." + owner_id, "runtime_task_id": "eq." + task_id,
        }, body={"status": "cancelled", "updated_at": datetime.now(timezone.utc).isoformat()})
        return {"task": final, "idempotent_replay": False}

    try:
        if lease_lost.is_set():
            raise AgentRuntimePersistenceError("WP-06 task lease was lost before social execution")
        cancelled = await finish_cancelled()
        if cancelled:
            return cancelled
        policy, grant = await _current_policy_and_grant(store, snapshot, owner_id, str(claimed["agent_id"]))
        agent = await store.get_agent(owner_id, str(claimed["agent_id"]))
        skill = await store.get_skill(owner_id, str(claimed["agent_id"]), str(claimed["skill_id"]))
        if (not agent or not skill or skill.get("status") != "published"
                or int(agent.get("version") or 0) != snapshot["agent_version"]
                or int(skill.get("version") or 0) != snapshot["skill_version"]):
            raise AgentSocialEventBlocked("SOCIAL_AGENT_OR_SKILL_VERSION_CHANGED")
        route_preflight = await router.preflight("internal")
        if route_preflight.get("route") != snapshot.get("route_snapshot"):
            raise AgentSocialEventBlocked("SOCIAL_MODEL_ROUTE_SNAPSHOT_CHANGED")
        reservation, lifecycle, approved_policy = await _reserve_social_credits(
            store, snapshot, owner_id, task_id,
        )
        if lease_lost.is_set():
            raise AgentRuntimePersistenceError("WP-06 task lease was lost after credit reservation")
        cancelled = await finish_cancelled()
        if cancelled:
            return cancelled
        effect_key = "social-generation:" + task_id
        effect_fingerprint = _sha({
            "task_id": task_id, "event_id": snapshot["correlation_id"],
            "snapshot_sha256": snapshot["snapshot_sha256"], "reservation_id": reservation.reservation_id,
        })
        existing_receipt = await store.get_effect_receipt(task_id, "social_generation", effect_key)
        if existing_receipt and existing_receipt.get("status") in {"started", "unknown"}:
            await lifecycle.complete(
                reservation=reservation, outcome=OperationOutcome.UNKNOWN, policy=approved_policy,
                idempotency_key="social-credit-settle:" + task_id,
                source_event_id="social-generation:" + task_id,
            )
            await store.mark_unknown_effect(owner_id, task_id)
            raise HTTPException(409, detail={"code": "SOCIAL_PROVIDER_OUTCOME_UNKNOWN"})
        if existing_receipt and existing_receipt.get("status") == "completed":
            provider_started = True
            result_payload = existing_receipt.get("result_payload")
            if not isinstance(result_payload, dict):
                raise AgentRuntimePersistenceError("WP-06 completed generation receipt has no result")
            evidence_payload = result_payload.get("provider_usage")
            output_text = result_payload.get("content")
        else:
            started = await store.begin_effect(
                owner_id, task_id, lease_token, task_version,
                "social_generation", effect_key, effect_fingerprint,
            )
            if not started:
                raise AgentRuntimePersistenceError("WP-06 provider effect start was not confirmed")
            provider_started = True
            context = snapshot["context"]
            prompt = (
                "Balas secara relevan, singkat, sopan, dan sesuai tone pemilik. "
                "Jangan mengklaim telah melakukan tindakan di luar percakapan. "
                "Jika pertanyaan membutuhkan keputusan manusia, nyatakan perlu ditinjau.\n\n"
                "Kanal: " + str(context["channel"]) + "\n"
                "Konteks konten pemilik: " + str(context["content_body"]) + "\n"
                "Pesan pengguna: " + str(context["source_body"]) + "\n"
                "Riwayat percakapan berizin: " + json.dumps(context.get("conversation_history") or [], ensure_ascii=False) + "\n"
                "Memory berizin: " + json.dumps(context.get("memory_context") or [], ensure_ascii=False)
            )
            system_prompt = (
                "Anda adalah AI Agent Allpha yang membalas atas nama pemilik dengan disclosure. "
                "Tone: " + str(snapshot["reply_tone"]) + ". Disclosure: " +
                str(snapshot["disclosure_text"]) + ". Dilarang membuka data privat, "
                "menebak fakta, atau melakukan publikasi tanpa approval manusia."
            )
            request = TextGenerationRequest(
                task_id=task_id, trace_id=str(snapshot["correlation_id"]),
                idempotency_key="social-generation:" + task_id,
                sensitivity="internal", prompt=prompt, system_prompt=system_prompt,
                max_output_tokens=min(500, int(snapshot["route_preflight"]["route"]["max_output_tokens"])),
                timeout_ms=min(30_000, int(snapshot["route_preflight"]["route"]["max_latency_ms"])),
                owner_id=owner_id, agent_id=str(claimed["agent_id"]),
                source_id=str(claimed["skill_id"]), source_version=int(claimed["skill_version"]),
                billing_account_id=owner_id,
            )
            response, evidence = await AgentRuntime().execute_skill_generation(
                requester_id=owner_id, owner_id=owner_id,
                agent_id=str(claimed["agent_id"]), agent_version=int(claimed["agent_version"]),
                skill_id=str(claimed["skill_id"]), skill_version=int(claimed["skill_version"]),
                skill_published=True, policy_version=router.policy_version_for("internal"),
                router=router, request=request, skill_tool_dependencies=(),
            )
            if lease_lost.is_set():
                await lifecycle.complete(
                    reservation=reservation, outcome=OperationOutcome.UNKNOWN, policy=approved_policy,
                    idempotency_key="social-credit-settle:" + task_id,
                    source_event_id="social-generation:" + task_id,
                )
                await store.mark_unknown_effect(owner_id, task_id)
                raise AgentRuntimePersistenceError(
                    "WP-06 task lease was lost during model execution; provider usage requires reconciliation"
                )
            output_text = response.output_text.strip()
            if not output_text or len(output_text) > int(snapshot["max_message_chars"]):
                raise AgentSocialEventBlocked("SOCIAL_GENERATED_OUTPUT_INVALID")
            evidence_payload = {
                "idempotency_key": evidence.idempotency_key,
                "input_tokens": evidence.input_tokens, "output_tokens": evidence.output_tokens,
                "cost_microunits": evidence.cost_microunits, "cost_unit": evidence.cost_unit,
                "pricing_version": evidence.pricing_version, "provider_id": evidence.provider_id,
                "model_id": evidence.model_id, "model_version": evidence.model_version,
                "evidence_sha256": evidence.evidence_sha256,
            }
            result_payload = {
                "content": output_text, "provider_usage": evidence_payload,
                "context_snapshot_sha256": snapshot["context_snapshot_sha256"],
                "memory_context_sha256": snapshot["memory_context_sha256"],
                "memory_context_refs": snapshot["context"].get("memory_context_refs") or [],
                "memory_policy_versions": snapshot.get("memory_policy_versions") or [],
            }
            completed_effect = await store.complete_effect(
                owner_id, task_id, lease_token, task_version,
                "social_generation", effect_key, effect_fingerprint, result_payload,
            )
            if not completed_effect:
                await lifecycle.complete(
                    reservation=reservation, outcome=OperationOutcome.UNKNOWN, policy=approved_policy,
                    idempotency_key="social-credit-settle:" + task_id,
                    source_event_id="social-generation:" + task_id,
                )
                await store.mark_unknown_effect(owner_id, task_id)
                raise AgentRuntimePersistenceError("WP-06 provider result receipt was not confirmed")

        if not isinstance(evidence_payload, dict) or not isinstance(output_text, str) or not output_text.strip():
            raise AgentRuntimePersistenceError("WP-06 recovered generation receipt is incomplete")
        usage_units = int(evidence_payload["input_tokens"]) + int(evidence_payload["output_tokens"])
        terms = snapshot["credit_terms"]
        actual_credits = usage_units * int(terms["credits_per_usage_unit"])
        if (usage_units <= 0 or usage_units > int(terms["estimated_usage_units"])
                or evidence_payload.get("cost_unit") != terms["cost_unit"]
                or evidence_payload.get("pricing_version") != snapshot["route_snapshot"]["pricing_version"]
                or int(evidence_payload["cost_microunits"]) > int(terms["estimated_cost_microunits"])):
            await lifecycle.complete(
                reservation=reservation, outcome=OperationOutcome.UNKNOWN, policy=approved_policy,
                idempotency_key="social-credit-settle:" + task_id,
                source_event_id=str(evidence_payload.get("idempotency_key") or effect_key),
            )
            raise AgentRuntimePersistenceError("WP-06 provider usage does not reconcile with the reserved policy")

        await _settle_social_reservation(
            store, lifecycle, reservation, approved_policy, owner_id=owner_id, task_id=task_id,
            evidence_payload=evidence_payload, actual_credits=actual_credits,
            actual_usage_units=usage_units, usage_unit=str(terms["usage_unit"]),
        )
        if lease_lost.is_set():
            raise AgentRuntimePersistenceError("WP-06 task lease was lost after provider metering settlement")
        cancelled = await finish_cancelled(provider_usage=evidence_payload)
        if cancelled:
            return cancelled
        moderator = load_generation_output_moderator()
        if moderator is None:
            raise AgentSocialEventBlocked("SOCIAL_OUTPUT_MODERATOR_UNAVAILABLE")
        moderation = await moderator.moderate(
            text=output_text,
            policy={"mode": "manual_review_only", "manual_review_only": True},
            metadata={"owner_id": owner_id, "agent_id": str(claimed["agent_id"]),
                      "task_id": task_id, "channel": str(snapshot["context"]["channel"])},
        )
        if moderation.get("decision") != "review_required":
            raise AgentSocialEventBlocked("SOCIAL_OUTPUT_MODERATION_POLICY_REJECTED")
        output_payload = {
            "content": output_text, "moderation": moderation, "approval_required": True,
            "provider_usage": evidence_payload, "credit_reservation_id": reservation.reservation_id,
            "credit_state": "settled", "route_snapshot": snapshot["route_snapshot"],
            "context_snapshot_sha256": snapshot["context_snapshot_sha256"],
            "memory_context_sha256": snapshot["memory_context_sha256"],
            "memory_context_refs": snapshot["context"].get("memory_context_refs") or [],
            "correlation_id": snapshot["correlation_id"],
            "idempotency_key": snapshot["idempotency_key"],
        }
        if lease_lost.is_set():
            raise AgentRuntimePersistenceError("WP-06 task lease was lost before draft finalization")
        cancelled = await finish_cancelled(provider_usage=evidence_payload)
        if cancelled:
            return cancelled
        final = await store.finalize_task(
            owner_id, task_id, lease_token, task_version, state="succeeded",
            output_payload=output_payload, error_code=None,
            event_log=list(claimed.get("event_log") or []) + [{
                "state": "succeeded", "at": datetime.now(timezone.utc).isoformat(),
                "trace_id": snapshot["correlation_id"], "reason_code": "social_reply_draft_ready",
            }],
        )
        if not final:
            raise AgentRuntimePersistenceError("WP-06 Agent Runtime task success was not confirmed")
        await store.request("PATCH", "agent_social_automation_runs", params={
            "owner_user_id": "eq." + owner_id, "runtime_task_id": "eq." + task_id,
        }, body={"status": "queued", "updated_at": datetime.now(timezone.utc).isoformat()})
        return {"task": final, "idempotent_replay": False}
    except AgentSocialEventBlocked as exc:
        if provider_started:
            if reservation and lifecycle and approved_policy:
                try:
                    await lifecycle.complete(
                        reservation=reservation, outcome=OperationOutcome.UNKNOWN, policy=approved_policy,
                        idempotency_key="social-credit-settle:" + task_id,
                        source_event_id="social-generation:" + task_id,
                    )
                except Exception:
                    logger.exception("WP-06 provider outcome could not transition reservation to pending reconciliation")
            await store.mark_unknown_effect(owner_id, task_id)
            raise AgentRuntimePersistenceError("WP-06 provider output is not durably reconciled; reservation remains pending") from exc
        if reservation and lifecycle and approved_policy:
            try:
                await lifecycle.complete(
                    reservation=reservation, outcome=OperationOutcome.FAILED_DEFINITIVE,
                    policy=approved_policy, idempotency_key="social-credit-release:" + task_id,
                    source_event_id="social-generation:" + task_id,
                )
            except Exception:
                logger.exception("WP-06 definitive failure credit release was not confirmed")
        final = await store.finalize_task(
            owner_id, task_id, lease_token, task_version, state="failed",
            output_payload={"reason_code": exc.reason_code}, error_code=exc.reason_code,
            event_log=list(claimed.get("event_log") or []) + [{
                "state": "failed", "at": datetime.now(timezone.utc).isoformat(),
                "trace_id": snapshot.get("correlation_id"), "reason_code": exc.reason_code,
            }],
        )
        await store.request("PATCH", "agent_social_automation_runs", params={
            "owner_user_id": "eq." + owner_id, "runtime_task_id": "eq." + task_id,
        }, body={"status": "failed", "updated_at": datetime.now(timezone.utc).isoformat()})
        return {"task": final, "idempotent_replay": False}
    except AgentRuntimeOutcomeUnknown:
        if reservation and lifecycle and approved_policy:
            try:
                await lifecycle.complete(
                    reservation=reservation, outcome=OperationOutcome.UNKNOWN, policy=approved_policy,
                    idempotency_key="social-credit-settle:" + task_id,
                    source_event_id="social-generation:" + task_id,
                )
            except Exception:
                logger.exception("WP-06 unknown provider outcome could not be marked pending in the Credit Ledger")
        await store.mark_unknown_effect(owner_id, task_id)
        raise
    except Exception as exc:
        if provider_started:
            if reservation and lifecycle and approved_policy:
                try:
                    await lifecycle.complete(
                        reservation=reservation, outcome=OperationOutcome.UNKNOWN, policy=approved_policy,
                        idempotency_key="social-credit-settle:" + task_id,
                        source_event_id="social-generation:" + task_id,
                    )
                except Exception:
                    logger.exception("WP-06 unknown provider outcome reservation could not be marked pending")
            await store.mark_unknown_effect(owner_id, task_id)
            raise AgentRuntimePersistenceError("WP-06 provider outcome requires reconciliation; automatic replay is blocked") from exc
        if reservation and lifecycle and approved_policy:
            try:
                await lifecycle.complete(
                    reservation=reservation, outcome=OperationOutcome.FAILED_DEFINITIVE,
                    policy=approved_policy, idempotency_key="social-credit-release:" + task_id,
                    source_event_id="social-generation:" + task_id,
                )
            except Exception:
                logger.exception("WP-06 pre-provider reservation release was not confirmed")
        raise
    finally:
        stop.set()
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass


async def reconcile_social_reply_approvals(store: AgentRuntimeStore, *, limit: int = 10) -> int:
    """Create/replay the canonical owner approval only after a persisted successful Agent Run."""
    if (os.getenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "false").lower() != "true"
            or os.getenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_WORKER_ENABLED", "false").lower() != "true"
            or not callable(getattr(store, "request", None))):
        return 0
    runs = await _rows(store, "agent_social_automation_runs", {
        "select": "id,owner_user_id,agent_id,runtime_task_id,source_event_id,channel,status",
        "status": "in.(queued,running)", "order": "created_at.asc",
        "limit": str(max(1, min(limit, 50))),
    })
    reconciled = 0
    for run in runs:
        if run.get("channel") not in {"comments", "mentions", "dm"}:
            continue
        task = await store.get_task(str(run["owner_user_id"]), str(run["runtime_task_id"]))
        if not task or task.get("state") != "succeeded":
            continue
        output = task.get("output_payload")
        if not isinstance(output, dict) or output.get("approval_required") is not True:
            continue
        event = await _one(store, "agent_social_automation_events", {
            "select": "*", "id": "eq." + str(run["source_event_id"]),
            "owner_user_id": "eq." + str(run["owner_user_id"]),
        })
        if not event:
            raise AgentRuntimePersistenceError("WP-06 successful run source event is missing")
        if run["channel"] == "dm":
            if not event.get("conversation_id") or not event.get("source_record_id"):
                raise AgentRuntimePersistenceError("WP-06 DM event is missing its canonical conversation/message target")
            result = await store.request("POST", "rpc/request_agent_social_message_draft", body={
                "p_owner_user_id": str(run["owner_user_id"]),
                "p_agent_id": str(run["agent_id"]),
                "p_runtime_task_id": str(run["runtime_task_id"]),
                "p_target_conversation_id": str(event["conversation_id"]),
                "p_target_message_id": str(event["source_record_id"]),
                "p_body": str(output.get("content") or ""),
                "p_idempotency_key": "social-auto-reply:" + str(event["id"]),
            })
        else:
            action_type = "draft_reply" if run["channel"] == "comments" else "draft_comment"
            result = await store.request("POST", "rpc/request_agent_social_draft", body={
                "p_owner_user_id": str(run["owner_user_id"]),
                "p_agent_id": str(run["agent_id"]),
                "p_runtime_task_id": str(run["runtime_task_id"]),
                "p_action_type": action_type,
                "p_content_type": "text", "p_visibility": "public",
                "p_body": str(output.get("content") or ""),
                "p_target_content_id": str(event["content_id"]) if event.get("content_id") else None,
                "p_target_comment_id": str(event["source_record_id"]) if run["channel"] == "comments" else None,
                "p_idempotency_key": "social-auto-reply:" + str(event["id"]),
            })
        if not isinstance(result, dict) or result.get("outcome") not in {"created", "replayed"}:
            raise AgentRuntimePersistenceError("WP-06 owner approval draft was not confirmed")
        await store.request("PATCH", "agent_social_automation_runs", params={
            "owner_user_id": "eq." + str(run["owner_user_id"]),
            "runtime_task_id": "eq." + str(run["runtime_task_id"]),
        }, body={"status": "awaiting_approval", "updated_at": datetime.now(timezone.utc).isoformat()})
        reconciled += 1
    return reconciled
