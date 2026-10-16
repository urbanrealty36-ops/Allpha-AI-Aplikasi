from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from allpha_api.skill_challenge_api import (
    CHALLENGE_ISSUE_LIMIT_PER_MINUTE, CHALLENGE_SUBMIT_LIMIT_PER_MINUTE,
    _canonical, _digest, _public_run, ChallengeIssue, ChallengeSubmit,
)


def test_canonical_digest_is_deterministic_and_key_order_independent():
    assert _canonical({"b": 2, "a": 1}) == _canonical({"a": 1, "b": 2})
    assert _digest({"b": 2, "a": 1}) == _digest({"a": 1, "b": 2})


def test_challenge_payloads_forbid_extra_fields_and_validate_idempotency():
    with pytest.raises(Exception):
        ChallengeIssue.model_validate({"agent_id": "00000000-0000-0000-0000-000000000001",
            "skill_id": "00000000-0000-0000-0000-000000000002", "test_key": "basic_test",
            "idempotency_key": "short", "owner_user_id": "untrusted"})
    with pytest.raises(Exception):
        ChallengeSubmit.model_validate({"nonce": "not valid nonce!", "submission": {}})


def test_public_projection_never_exposes_expected_output_nonce_or_snapshot():
    projected = _public_run({
        "id": "run", "status": "issued", "expected_output": {"secret": True},
        "nonce_hash": "hash", "skill_snapshot": {"instructions": "private"},
        "challenge_input": {"question": "hello"}, "agent_version": 3,
    })
    assert projected["challenge_input"] == {"question": "hello"}
    assert "expected_output" not in projected and "nonce_hash" not in projected and "skill_snapshot" not in projected


def test_digest_uses_sha256_hex():
    assert len(_digest({"x": 1})) == 64
    assert all(ch in "0123456789abcdef" for ch in _digest({"x": 1}))


def test_json_canonicalization_rejects_nan():
    with pytest.raises(ValueError):
        _canonical({"score": float("nan")})


def test_challenge_rate_limits_are_bounded_and_submission_limit_is_defined():
    assert 1 <= CHALLENGE_ISSUE_LIMIT_PER_MINUTE <= 60
    assert 1 <= CHALLENGE_SUBMIT_LIMIT_PER_MINUTE <= 60
    assert CHALLENGE_SUBMIT_LIMIT_PER_MINUTE >= CHALLENGE_ISSUE_LIMIT_PER_MINUTE


def test_challenge_issue_supports_server_selected_hidden_case():
    payload = ChallengeIssue.model_validate({
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "skill_id": "00000000-0000-0000-0000-000000000002",
        "test_key": None,
        "idempotency_key": "hidden-case-idempotency-01",
    })
    assert payload.test_key is None


from datetime import timedelta
from uuid import UUID, uuid4

from allpha_api import skill_challenge_api as challenge_api
from allpha_api.evaluation_engine import EVALUATOR_VERSION


class FakeChallengeStore:
    def __init__(self):
        self.owner_id = "00000000-0000-0000-0000-000000000010"
        self.agent_id = "00000000-0000-0000-0000-000000000011"
        self.skill_id = "00000000-0000-0000-0000-000000000012"
        self.agent = {
            "id": self.agent_id, "version": 4, "status": "active", "handle": "agent_test",
            "display_name": "Agent Test", "description": "test", "avatar_url": None,
            "persona": {}, "disclosure": "AI", "boundaries": {}, "visibility": "private",
            "created_by": self.owner_id, "created_at": "2026-10-16T00:00:00+00:00",
            "updated_at": "2026-10-16T00:00:00+00:00",
        }
        self.rubric = {
            "rubric_key": "challenge_task", "version": 1,
            "criteria": [{"key": "task_success", "weight": 1.0, "required": True, "minimum_score": 1.0}],
            "pass_threshold": 1.0, "evaluator_version": EVALUATOR_VERSION,
        }
        self.snapshot = {
            "id": self.skill_id, "agent_id": self.agent_id, "version": 2,
            "name": "Skill Test", "slug": "skill_test", "status": "draft", "created_by": self.owner_id,
            "tests": [
                {"key": "visible_case", "input": {"question": "2+2?"}, "expected_output": {"answer": "4"}},
                {"key": "hidden_case", "hidden": True, "input": {"question": "3+3?"}, "expected_output": {"answer": "6"}},
            ],
            "evaluation_rubric": self.rubric,
        }
        self.skill = {**self.snapshot, "category": "test", "description": "test", "instructions": "test",
            "inputs_schema": {}, "outputs_schema": {}, "constraints": {}, "tool_dependencies": [],
            "required_permission_scopes": [], "model_requirements": {}, "budget_limits": {},
            "provenance": {}, "changelog": "", "publication_terms": {}, "updated_at": "2026-10-16T00:00:00+00:00"}
        self.run = None
        self.achievement = None

    async def get_agent(self, owner_id: str, agent_id: str):
        if owner_id != self.owner_id or agent_id != self.agent_id:
            return None
        return {"id": self.agent_id, "version": 4, "status": "active", "created_by": self.owner_id}

    async def request(self, method, path, params=None, body=None, prefer=None):
        params = params or {}
        if method == "GET" and path == "agent_skill_challenge_runs":
            if self.run and params.get("id") == f"eq.{self.run['id']}":
                if params.get("owner_user_id") == f"eq.{self.owner_id}":
                    return [dict(self.run)]
            if self.run and params.get("idempotency_key") == f"eq.{self.run['idempotency_key']}":
                return [dict(self.run)]
            if params.get("submission_fingerprint") and self.run and self.run.get("submission_fingerprint") == params["submission_fingerprint"]:
                return []
            return []
        if method == "GET" and path == "agent_skills":
            return [dict(self.skill)] if params.get("id") == f"eq.{self.skill_id}" and params.get("agent_id") == f"eq.{self.agent_id}" else []
        if method == "GET" and path == "ai_agents":
            return [dict(self.agent)] if params.get("id") == f"eq.{self.agent_id}" else []
        if method == "GET" and path == "agent_skill_versions":
            return [{"id": "00000000-0000-0000-0000-000000000013", "skill_id": self.skill_id,
                "agent_id": self.agent_id, "version": 2, "snapshot": self.snapshot}]
        if method == "POST" and path == "rpc/reserve_agent_skill_challenge_action":
            return True
        if method == "POST" and path == "agent_skill_challenge_runs":
            self.run = {**body, "id": str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat()}
            return [dict(self.run)]
        if method == "PATCH" and path == "agent_skill_challenge_runs":
            if not self.run or params.get("id") != f"eq.{self.run['id']}" or params.get("owner_user_id") != f"eq.{self.owner_id}":
                return []
            if params.get("status") and params["status"] != f"eq.{self.run['status']}":
                return []
            if params.get("nonce_hash") and params["nonce_hash"] != f"eq.{self.run['nonce_hash']}":
                return []
            self.run.update(body or {})
            return [dict(self.run)]
        if method == "POST" and path == "agent_skill_challenge_achievement_evidence":
            self.achievement = {**body, "awarded_at": datetime.now(timezone.utc).isoformat()}
            return [dict(self.achievement)]
        if method == "GET" and path == "agent_skill_challenge_achievement_evidence":
            if self.achievement and self.achievement["challenge_run_id"] == params.get("challenge_run_id", "").removeprefix("eq."):
                return [dict(self.achievement)]
            return []
        raise AssertionError(f"Unexpected fake store request: {method} {path} {params}")


@pytest.mark.asyncio
async def test_issue_hidden_challenge_pins_versions_and_never_returns_expected_output(monkeypatch):
    store = FakeChallengeStore()
    monkeypatch.setattr(challenge_api, "_store", lambda: store)
    result = await challenge_api.issue_challenge(
        ChallengeIssue(agent_id=UUID(store.agent_id), skill_id=UUID(store.skill_id),
            test_key=None, idempotency_key="hidden-challenge-issue-01"),
        request=None, user={"id": store.owner_id},
    )
    assert result["run"]["challenge_key"] == "hidden_case"
    assert result["run"]["agent_version"] == 4
    assert result["run"]["skill_version"] == 2
    assert result["run"]["evaluation_set_version"] == 2
    assert result["nonce"]
    assert "expected_output" not in result["run"]
    assert "skill_snapshot" not in result["run"]


@pytest.mark.asyncio
async def test_submit_challenge_persists_repeatable_evidence_and_rejects_conflicting_replay(monkeypatch):
    store = FakeChallengeStore()
    monkeypatch.setattr(challenge_api, "_store", lambda: store)
    issued = await challenge_api.issue_challenge(
        ChallengeIssue(agent_id=UUID(store.agent_id), skill_id=UUID(store.skill_id),
            test_key="visible_case", idempotency_key="visible-challenge-issue-01"),
        request=None, user={"id": store.owner_id},
    )
    run_id = UUID(issued["run"]["id"])
    submitted = await challenge_api.submit_challenge(
        run_id, ChallengeSubmit(nonce=issued["nonce"], submission={"answer": "4"}),
        user={"id": store.owner_id},
    )
    assert submitted["run"]["status"] == "passed"
    assert submitted["run"]["evidence_digest"]
    assert submitted["achievement"]["key"] == "skill_challenge_passed"
    replay = await challenge_api.submit_challenge(
        run_id, ChallengeSubmit(nonce=issued["nonce"], submission={"answer": "4"}),
        user={"id": store.owner_id},
    )
    assert replay["idempotent_replay"] is True
    with pytest.raises(HTTPException) as error:
        await challenge_api.submit_challenge(
            run_id, ChallengeSubmit(nonce=issued["nonce"], submission={"answer": "different"}),
            user={"id": store.owner_id},
        )
    assert error.value.status_code == 409
