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
