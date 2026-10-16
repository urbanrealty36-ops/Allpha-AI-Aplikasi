from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from allpha_api.skill_challenge_api import _canonical, _digest, _public_run, ChallengeIssue, ChallengeSubmit


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
