from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from allpha_api import skill_challenge_execution_api as execution_api


class ChallengeRunStore:
    def __init__(self, row):
        self.row = row

    async def request(self, method, path, params=None, body=None, prefer=None):
        if method == "GET" and path == "agent_skill_challenge_runs":
            if params.get("owner_user_id") == "eq.owner-1" and params.get("id") == f"eq.{self.row['id']}":
                return [dict(self.row)]
        raise AssertionError(f"Unexpected store request: {method} {path}")


def test_execute_challenge_fails_closed_when_deployment_has_no_model_router(monkeypatch):
    async def scenario():
        nonce = "A" * 48
        row = {
            "id": "00000000-0000-0000-0000-000000000010",
            "owner_user_id": "owner-1",
            "agent_id": "00000000-0000-0000-0000-000000000011",
            "agent_version": 1,
            "skill_id": "00000000-0000-0000-0000-000000000012",
            "skill_version": 1,
            "status": "issued",
            "nonce_hash": hashlib.sha256(nonce.encode()).hexdigest(),
            "nonce_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            "skill_snapshot": {
                "id": "00000000-0000-0000-0000-000000000012",
                "version": 1,
                "instructions": "Answer the provided test input.",
                "status": "published",
            },
            "challenge_input": {"question": "test"},
            "idempotency_key": "challenge-idempotency-1",
            "runtime_evidence": None,
        }
        monkeypatch.setattr(execution_api, "_store", lambda: ChallengeRunStore(row))
        request = SimpleNamespace(
            headers={},
            app=SimpleNamespace(state=SimpleNamespace()),
        )
        with pytest.raises(HTTPException) as error:
            await execution_api.execute_skill_challenge(
                UUID(row["id"]),
                execution_api.ChallengeExecute(nonce=nonce),
                request,
                user={"id": "owner-1"},
            )
        assert error.value.status_code == 503
        assert error.value.detail["code"] == "TEXT_GENERATION_ROUTE_UNAVAILABLE"

    asyncio.run(scenario())


def test_owner_release_decision_requires_valid_explicit_reason():
    with pytest.raises(Exception):
        execution_api.OwnerReleaseDecision(decision="release", reason="ok")
    decision = execution_api.OwnerReleaseDecision(decision="hold", reason="Hold until evaluation evidence is reviewed.")
    assert decision.decision == "hold"


def test_challenge_execute_payload_rejects_extra_privilege_fields():
    with pytest.raises(Exception):
        execution_api.ChallengeExecute.model_validate({"nonce": "A" * 48, "owner_user_id": "attacker"})

class DecisionStore:
    def __init__(self, current, previous=None):
        self.current = dict(current)
        self.previous = list(previous or [])
        self.requests = []

    async def request(self, method, path, params=None, body=None, prefer=None):
        params = params or {}
        self.requests.append((method, path, dict(params), dict(body or {})))
        if path != "agent_skill_challenge_runs":
            raise AssertionError(f"Unexpected store path: {path}")

        if method == "GET":
            if params.get("id") and params.get("owner_user_id"):
                if (
                    params["id"] == f"eq.{self.current['id']}"
                    and params["owner_user_id"] == f"eq.{self.current['owner_user_id']}"
                ):
                    return [dict(self.current)]
                return []
            if params.get("skill_id"):
                return [dict(row) for row in self.previous]
            raise AssertionError(f"Unexpected GET filters: {params}")

        if method == "PATCH":
            same_run = (
                params.get("id") == f"eq.{self.current['id']}"
                and params.get("owner_user_id") == f"eq.{self.current['owner_user_id']}"
                and params.get("runtime_evidence_digest") == f"eq.{self.current.get('runtime_evidence_digest')}"
            )
            if same_run and "previous_version_comparison" in (body or {}):
                self.current.update(body or {})
                return [dict(self.current)]
            if (
                same_run
                and params.get("release_decision") == "is.null"
                and self.current.get("release_decision") is None
            ):
                self.current.update(body or {})
                return [dict(self.current)]
            return []

        raise AssertionError(f"Unexpected store request: {method} {path}")


def _decision_run(**overrides):
    row = {
        "id": "00000000-0000-0000-0000-000000000020",
        "owner_user_id": "owner-1",
        "agent_id": "agent-1",
        "skill_id": "skill-1",
        "skill_version": 3,
        "challenge_key": "case-basic",
        "status": "passed",
        "evaluation_result": {"score": 0.95},
        "evidence_digest": "eval-digest-v3",
        "runtime_output": {"answer": "new"},
        "runtime_evidence": {"provider_id": "provider-test"},
        "runtime_evidence_digest": "runtime-digest-v3",
        "previous_version_comparison": None,
        "release_decision": None,
        "release_decision_reason": None,
        "release_decided_by": None,
        "release_decided_at": None,
    }
    row.update(overrides)
    return row


def test_version_comparison_persists_pinned_prior_version_evidence(monkeypatch):
    async def scenario():
        current = _decision_run()
        previous = {
            "id": "00000000-0000-0000-0000-000000000019",
            "skill_version": 2,
            "status": "passed",
            "evaluation_result": {"score": 0.8},
            "evidence_digest": "eval-digest-v2",
            "runtime_evidence_digest": "runtime-digest-v2",
            "runtime_output": {"answer": "old"},
            "created_at": "2026-10-15T10:00:00+00:00",
        }
        store = DecisionStore(current, [previous])
        monkeypatch.setattr(execution_api, "_store", lambda: store)

        result = await execution_api.compare_skill_version(
            UUID(current["id"]), user={"id": "owner-1"}
        )

        comparison = result["comparison"]
        assert comparison["previous_run_id"] == previous["id"]
        assert comparison["previous_skill_version"] == 2
        assert comparison["current_skill_version"] == 3
        assert comparison["score_delta"] == pytest.approx(0.15)
        assert comparison["output_changed"] is True
        assert comparison["decision_required"] is True
        assert store.current["previous_version_comparison"] == comparison
        patch_calls = [call for call in store.requests if call[0] == "PATCH"]
        assert len(patch_calls) == 1
        assert patch_calls[0][2]["runtime_evidence_digest"] == "eq.runtime-digest-v3"

    asyncio.run(scenario())


def test_version_comparison_is_owner_scoped(monkeypatch):
    async def scenario():
        current = _decision_run()
        store = DecisionStore(current, [])
        monkeypatch.setattr(execution_api, "_store", lambda: store)

        with pytest.raises(HTTPException) as error:
            await execution_api.compare_skill_version(
                UUID(current["id"]), user={"id": "different-owner"}
            )

        assert error.value.status_code == 404
        assert error.value.detail["code"] == "CHALLENGE_RUN_NOT_FOUND"
        assert not any(call[0] == "PATCH" for call in store.requests)

    asyncio.run(scenario())


def test_owner_release_decision_persists_once_and_replays_idempotently(monkeypatch):
    async def scenario():
        current = _decision_run(previous_version_comparison={
            "comparison_version": "eng-p12-version-comparison-v1",
            "current_skill_version": 3,
            "previous_skill_version": 2,
            "current_score": 0.95,
            "previous_score": 0.8,
        })
        store = DecisionStore(current)
        monkeypatch.setattr(execution_api, "_store", lambda: store)
        payload = execution_api.OwnerReleaseDecision(
            decision="release",
            reason="Version passed evaluation and improved against the prior version.",
        )

        first = await execution_api.record_owner_release_decision(
            UUID(current["id"]), payload, user={"id": "owner-1"}
        )
        second = await execution_api.record_owner_release_decision(
            UUID(current["id"]), payload, user={"id": "owner-1"}
        )

        assert first["idempotent_replay"] is False
        assert first["publication_performed"] is False
        assert first["run"]["release_decision"] == "release"
        assert first["run"]["release_decided_by"] == "owner-1"
        assert store.current["release_decided_at"]
        assert second["idempotent_replay"] is True
        assert second["publication_performed"] is False
        assert len([call for call in store.requests if call[0] == "PATCH"]) == 1

    asyncio.run(scenario())


def test_owner_release_decision_rejects_release_without_version_comparison(monkeypatch):
    async def scenario():
        current = _decision_run(previous_version_comparison=None)
        store = DecisionStore(current)
        monkeypatch.setattr(execution_api, "_store", lambda: store)

        with pytest.raises(HTTPException) as error:
            await execution_api.record_owner_release_decision(
                UUID(current["id"]),
                execution_api.OwnerReleaseDecision(
                    decision="release",
                    reason="Attempt release before comparing the prior version.",
                ),
                user={"id": "owner-1"},
            )

        assert error.value.status_code == 409
        assert error.value.detail["code"] == "RELEASE_GATES_NOT_MET"
        assert not any(call[0] == "PATCH" for call in store.requests)

    asyncio.run(scenario())


def test_owner_release_decision_rejects_conflicting_second_decision(monkeypatch):
    async def scenario():
        current = _decision_run(
            release_decision="hold",
            release_decision_reason="Hold pending additional evaluation evidence.",
            release_decided_by="owner-1",
            release_decided_at="2026-10-16T10:00:00+00:00",
        )
        store = DecisionStore(current)
        monkeypatch.setattr(execution_api, "_store", lambda: store)

        with pytest.raises(HTTPException) as error:
            await execution_api.record_owner_release_decision(
                UUID(current["id"]),
                execution_api.OwnerReleaseDecision(
                    decision="release",
                    reason="Attempt to replace an existing hold decision.",
                ),
                user={"id": "owner-1"},
            )

        assert error.value.status_code == 409
        assert error.value.detail["code"] == "RELEASE_DECISION_ALREADY_RECORDED"
        assert store.current["release_decision"] == "hold"
        assert not any(call[0] == "PATCH" for call in store.requests)

    asyncio.run(scenario())

