from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from allpha_api.agent_social_api import CoauthoredDraft, PolicyWrite


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
