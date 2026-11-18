from __future__ import annotations

import asyncio
import uuid

import pytest
from pydantic import ValidationError

from fastapi import HTTPException

from allpha_api import agent_social_api
from allpha_api.agent_social_api import (AutomationPolicyWrite, CoauthoredDraft, PolicyWrite, TakeoverWrite)


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
