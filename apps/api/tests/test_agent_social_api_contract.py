from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fastapi import HTTPException

from allpha_api import agent_social_api
from allpha_api.agent_social_api import (ApprovalDecision, AutomationGrantRevoke, AutomationGrantWrite, AutomationPolicyWrite, CoauthoredDraft, PolicyWrite, TakeoverWrite)


AGENT = uuid.UUID("00000000-0000-0000-0000-000000000001")
TASK = uuid.UUID("00000000-0000-0000-0000-000000000002")
CONTENT = uuid.UUID("00000000-0000-0000-0000-000000000003")
COMMENT = uuid.UUID("00000000-0000-0000-0000-000000000004")


def draft(**overrides) -> CoauthoredDraft:
    values = {
        "agent_id": AGENT,
        "runtime_task_id": TASK,
        "idempotency_key": "agent-social-001",
    }
    values.update(overrides)
    return CoauthoredDraft(**values)


def test_agent_social_draft_post_is_not_allowed_to_smuggle_a_target():
    assert draft().action_type == "draft_post"
    with pytest.raises(ValidationError):
        draft(target_content_id=CONTENT)


def test_agent_social_comment_and_reply_require_exact_targets():
    assert draft(action_type="draft_comment", target_content_id=CONTENT).target_content_id == CONTENT
    with pytest.raises(ValidationError):
        draft(action_type="draft_comment")
    assert draft(action_type="draft_reply", target_content_id=CONTENT,
                 target_comment_id=COMMENT).target_comment_id == COMMENT
    with pytest.raises(ValidationError):
        draft(action_type="draft_reply", target_content_id=CONTENT)


def test_agent_social_repost_requires_a_target_and_text_payload():
    assert draft(action_type="suggest_repost", target_content_id=CONTENT).target_content_id == CONTENT
    with pytest.raises(ValidationError):
        draft(action_type="suggest_repost")
    with pytest.raises(ValidationError):
        draft(action_type="suggest_repost", target_content_id=CONTENT, content_type="video")


def test_agent_social_story_reply_requires_a_story_target():
    assert draft(action_type="draft_story", target_content_id=CONTENT,
                 content_type="story").content_type == "story"
    with pytest.raises(ValidationError):
        draft(action_type="draft_story", target_content_id=CONTENT)


def test_unsupported_high_risk_only_approval_mode_is_rejected():
    with pytest.raises(ValidationError):
        PolicyWrite(approval_mode="high_risk_only")



def test_automation_read_is_safe_when_schema_is_not_active(monkeypatch):
    async def owned(owner_id, agent_id):
        return {"id": agent_id}

    async def forbidden_db(*args, **kwargs):
        raise AssertionError("automation schema must not be queried while its feature gate is off")

    monkeypatch.setattr(agent_social_api, "_active_owned_agent", owned)
    monkeypatch.setattr(agent_social_api, "_server_db", forbidden_db)
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "false")

    result = asyncio.run(agent_social_api.get_automation(AGENT, {"id": str(uuid.uuid4())}))

    assert result["policy"] is None
    assert result["auto_reply_runtime_enabled"] is False
    assert result["runtime_reason"] == "AGENT_SOCIAL_AUTOMATION_SCHEMA_NOT_ACTIVE"


def test_automation_mutations_fail_closed_until_schema_is_active(monkeypatch):
    async def owned(owner_id, agent_id):
        return {"id": agent_id}

    async def forbidden_db(*args, **kwargs):
        raise AssertionError("automation schema must not be queried while its feature gate is off")

    monkeypatch.setattr(agent_social_api, "_active_owned_agent", owned)
    monkeypatch.setattr(agent_social_api, "_server_db", forbidden_db)
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "false")
    owner = {"id": str(uuid.uuid4())}

    with pytest.raises(HTTPException) as put_error:
        asyncio.run(agent_social_api.put_automation(
            AGENT, AutomationPolicyWrite(expected_version=1), owner,
        ))
    assert put_error.value.status_code == 503
    assert put_error.value.detail["code"] == "AGENT_SOCIAL_AUTOMATION_SCHEMA_NOT_ACTIVE"

    with pytest.raises(HTTPException) as takeover_error:
        asyncio.run(agent_social_api.set_takeover(
            AGENT, TakeoverWrite(takeover_active=True), owner,
        ))
    assert takeover_error.value.status_code == 503
    assert takeover_error.value.detail["code"] == "AGENT_SOCIAL_AUTOMATION_SCHEMA_NOT_ACTIVE"



def test_agent_social_dispatch_migration_preserves_notification_preferences_and_agent_dm_kind():
    migration = Path(__file__).parents[1] / "supabase" / "source-only-migrations" / "20261118190000_wp06_agent_social_action_attribution_and_dispatch.sql"
    assert migration.is_file(), "WP-06 dispatch migration must remain in the source-only quarantine until its activation gate is met"
    assert not (Path(__file__).parents[1] / "supabase" / "migrations" / migration.name).exists()
    sql = migration.read_text(encoding="utf-8")

    assert "actor_agent_id" in sql
    assert "agent_disclosure_snapshot" in sql
    assert "values('agent','Balasan Story',p_owner_user_id)" in sql
    assert "agent_social_notification_state(p_owner_user_id)" in sql
    assert "agent_social_notification_state(v_recipient)" in sql
    assert "insert into public.agent_social_audit_events" in sql
    assert "set status = 'review', moderation_status = 'pending'" in sql



def test_social_dispatch_approval_fails_closed_when_schema_flag_is_off(monkeypatch):
    calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, body))
        if method == "GET":
            return [{"id": str(CONTENT), "action_type": "draft_comment", "status": "pending"}]
        raise AssertionError("dispatch RPC must not run while the schema flag is off")

    monkeypatch.setattr(agent_social_api, "_server_db", fake_db)
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_ACTION_DISPATCH_ENABLED", "false")
    with pytest.raises(HTTPException) as error:
        asyncio.run(agent_social_api.decide_approval(
            CONTENT, ApprovalDecision(decision="approve"), {"id": str(uuid.uuid4())},
        ))
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "AGENT_SOCIAL_ACTION_SCHEMA_NOT_ACTIVE"
    assert len(calls) == 1


def test_already_approved_social_action_can_be_idempotently_replayed_when_flag_is_off(monkeypatch):
    calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, body))
        if method == "GET":
            return [{"id": str(CONTENT), "action_type": "draft_comment", "status": "approved"}]
        assert table == "rpc/approve_agent_social_action_for_runtime"
        return {"outcome": "replayed", "approval": {"id": str(CONTENT), "status": "approved",
                "dispatch_task_id": str(TASK)},
                "execution": {"kind": "pending_agent_runtime", "dispatch_task_id": str(TASK)}}

    monkeypatch.setattr(agent_social_api, "_server_db", fake_db)
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_ACTION_DISPATCH_ENABLED", "false")
    result = asyncio.run(agent_social_api.decide_approval(
        CONTENT, ApprovalDecision(decision="approve"), {"id": str(uuid.uuid4())},
    ))
    assert result["outcome"] == "replayed"
    assert result["approval_complete"] is True
    assert result["execution_pending"] is True
    assert result["dispatch_task_id"] == str(TASK)
    assert len(calls) == 2




def test_social_approval_dispatch_uses_runtime_rpc_for_comment_reply_and_story(monkeypatch):
    for action in ("draft_comment", "draft_reply", "draft_story"):
        calls = []
        async def fake_db(method, table, *, params=None, body=None, prefer=None):
            calls.append((method, table, body))
            if method == "GET":
                return [{"id": str(CONTENT), "action_type": action, "status": "pending"}]
            return {"outcome": "approved",
                    "approval": {"id": str(CONTENT), "status": "approved",
                                 "dispatch_task_id": str(TASK)},
                    "execution": {"kind": "pending_agent_runtime",
                                  "dispatch_task_id": str(TASK),
                                  "next_action": "agent_runtime_worker"},
                    "dispatch_task": {"id": str(TASK), "state": "queued"}}
        monkeypatch.setattr(agent_social_api, "_server_db", fake_db)
        monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_ACTION_DISPATCH_ENABLED", "true")
        result = asyncio.run(agent_social_api.decide_approval(
            CONTENT, ApprovalDecision(decision="approve"), {"id": str(uuid.uuid4())},
        ))
        assert calls[1][1] == "rpc/approve_agent_social_action_for_runtime"
        assert result["execution_pending"] is True
        assert result["dispatch_task_id"] == str(TASK)

def test_automation_grant_contract_rejects_duplicate_or_expired_scopes():
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    with pytest.raises(ValidationError):
        AutomationGrantWrite(
            granted_scopes=["comments", "comments"],
            idempotency_key="social-grant-001", expires_at=future,
        )
    with pytest.raises(ValidationError):
        AutomationGrantWrite(
            granted_scopes=["comments"],
            idempotency_key="social-grant-002",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )


def test_automation_grant_read_is_safe_when_schema_is_not_active(monkeypatch):
    async def owned(owner_id, agent_id):
        return {"id": agent_id}

    async def forbidden_db(*args, **kwargs):
        raise AssertionError("automation grant schema must not be queried while its feature gate is off")

    monkeypatch.setattr(agent_social_api, "_active_owned_agent", owned)
    monkeypatch.setattr(agent_social_api, "_server_db", forbidden_db)
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "false")

    result = asyncio.run(agent_social_api.list_automation_grants(
        AGENT, {"id": str(uuid.uuid4())},
    ))
    assert result == {"items": [], "schema_active": False, "auto_reply_runtime_enabled": False}


def test_automation_grant_create_and_revoke_fail_closed_until_schema_is_active(monkeypatch):
    async def owned(owner_id, agent_id):
        return {"id": agent_id}

    async def forbidden_db(*args, **kwargs):
        raise AssertionError("automation grant schema must not be queried while its feature gate is off")

    monkeypatch.setattr(agent_social_api, "_active_owned_agent", owned)
    monkeypatch.setattr(agent_social_api, "_server_db", forbidden_db)
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "false")
    owner = {"id": str(uuid.uuid4())}
    grant = AutomationGrantWrite(
        granted_scopes=["comments"], idempotency_key="social-grant-003",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    with pytest.raises(HTTPException) as create_error:
        asyncio.run(agent_social_api.create_automation_grant(AGENT, grant, owner))
    assert create_error.value.status_code == 503

    with pytest.raises(HTTPException) as revoke_error:
        asyncio.run(agent_social_api.revoke_automation_grant(
            AGENT, uuid.uuid4(), AutomationGrantRevoke(), owner,
        ))
    assert revoke_error.value.status_code == 503
