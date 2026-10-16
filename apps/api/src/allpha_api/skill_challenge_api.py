"""Authenticated Skill Challenge, deterministic evaluation, and achievement evidence API.

The API pins persisted Agent/Skill versions and the rubric/evaluation-set digest at
issuance. Submissions are one-shot, idempotent, owner-scoped and fail closed.
This module does not execute arbitrary Skill instructions or issue monetary/credit
rewards. Reward settlement remains owned by the canonical financial ledger.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user
from allpha_api.agent_runtime_store import AgentRuntimeStore, AgentRuntimePersistenceError
from allpha_api.evaluation_engine import (
    EVALUATOR_VERSION, CriterionSignal, EvaluationRubric, evaluate_submission,
)

router = APIRouter(prefix="/v1/skill-challenges", tags=["skill-challenges"])
MAX_JSON_BYTES = 32_768
NONCE_TTL_SECONDS = 900


class ChallengeIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: uuid.UUID
    skill_id: uuid.UUID
    test_key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9_-]+$")
    idempotency_key: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")


class ChallengeSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nonce: str = Field(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    submission: dict[str, Any] = Field(max_length=100)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _store() -> AgentRuntimeStore:
    try:
        return AgentRuntimeStore.from_environment()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={"code": "CHALLENGE_STORAGE_NOT_CONFIGURED", "message": "Penyimpanan Skill Challenge belum dikonfigurasi."}) from exc


def _storage_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail={"code": "CHALLENGE_STORAGE_UNAVAILABLE", "message": "Status penyimpanan Skill Challenge tidak dapat dipastikan."}) from exc


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _public_run(row: dict[str, Any]) -> dict[str, Any]:
    # Expected output, full skill snapshot, nonce hash and raw challenge internals are never returned.
    return {
        key: row.get(key) for key in (
            "id", "agent_id", "skill_id", "agent_version", "skill_version",
            "challenge_key", "evaluation_set_version", "evaluation_set_digest",
            "rubric_key", "rubric_version", "rubric_digest", "evaluator_version",
            "challenge_input", "status", "evaluation_result", "evidence_digest",
            "submitted_at", "completed_at", "created_at", "updated_at",
        )
    }


async def _owned_agent_and_skill(store: AgentRuntimeStore, owner_id: str, agent_id: str, skill_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    agent = await store.get_agent(owner_id, agent_id)
    if not agent or agent.get("status") == "archived":
        raise HTTPException(status_code=404, detail={"code": "AGENT_NOT_FOUND", "message": "Agent tidak ditemukan."})
    rows = await store.request("GET", "agent_skills", params={
        "select": "id,agent_id,created_by,slug,name,description,category,inputs_schema,outputs_schema,instructions,constraints,tool_dependencies,required_permission_scopes,model_requirements,budget_limits,tests,evaluation_rubric,provenance,version,changelog,publication_terms,status,created_at,updated_at",
        "id": f"eq.{skill_id}", "agent_id": f"eq.{agent_id}", "limit": "1",
    })
    if not rows or rows[0].get("status") == "archived":
        raise HTTPException(status_code=404, detail={"code": "SKILL_NOT_FOUND", "message": "Skill tidak ditemukan."})
    return agent, rows[0]


async def _get_run(store: AgentRuntimeStore, owner_id: str, run_id: str) -> dict[str, Any] | None:
    rows = await store.request("GET", "agent_skill_challenge_runs", params={
        "select": "*", "id": f"eq.{run_id}", "owner_user_id": f"eq.{owner_id}", "limit": "1",
    })
    return rows[0] if rows else None


@router.post("/runs", status_code=201)
async def issue_challenge(payload: ChallengeIssue, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    try:
        existing = await store.request("GET", "agent_skill_challenge_runs", params={
            "select": "*", "owner_user_id": f"eq.{owner_id}", "idempotency_key": f"eq.{payload.idempotency_key}", "limit": "1",
        })
        agent, skill = await _owned_agent_and_skill(store, owner_id, str(payload.agent_id), str(payload.skill_id))
        fingerprint = _digest({
            "agent_id": str(payload.agent_id), "skill_id": str(payload.skill_id),
            "test_key": payload.test_key,
        })
        if existing:
            row = existing[0]
            if row.get("request_fingerprint") != fingerprint:
                raise HTTPException(status_code=409, detail={"code": "CHALLENGE_IDEMPOTENCY_CONFLICT", "message": "Idempotency key sudah dipakai untuk challenge berbeda."})
            return {"run": _public_run(row), "idempotent_replay": True}

        version_rows = await store.request("GET", "agent_skill_versions", params={
            "select": "id,skill_id,agent_id,version,snapshot,created_at",
            "skill_id": f"eq.{skill['id']}", "agent_id": f"eq.{agent['id']}",
            "version": f"eq.{skill['version']}", "limit": "1",
        })
        version_row = version_rows[0] if version_rows else None
        snapshot = (version_row or {}).get("snapshot") or skill
        if int(snapshot.get("version") or 0) != int(skill.get("version") or 0):
            raise HTTPException(status_code=409, detail={"code": "SKILL_VERSION_SNAPSHOT_MISMATCH", "message": "Snapshot Skill tidak cocok dengan versi aktif."})
        tests = snapshot.get("tests")
        if not isinstance(tests, list) or not tests:
            raise HTTPException(status_code=422, detail={"code": "CHALLENGE_TEST_SET_MISSING", "message": "Skill belum memiliki evaluation set yang dapat dijalankan."})
        case = next((item for item in tests if isinstance(item, dict) and item.get("key") == payload.test_key), None)
        if not case:
            raise HTTPException(status_code=404, detail={"code": "CHALLENGE_TEST_NOT_FOUND", "message": "Test case tidak ditemukan pada versi Skill ini."})
        challenge_input = case.get("input", case.get("inputs"))
        expected_output = case.get("expected_output", case.get("expected"))
        if not isinstance(challenge_input, dict) or not isinstance(expected_output, dict):
            raise HTTPException(status_code=422, detail={"code": "CHALLENGE_TEST_CASE_INVALID", "message": "Test case harus memiliki input dan expected_output berbentuk object."})
        rubric_raw = snapshot.get("evaluation_rubric")
        if not isinstance(rubric_raw, dict) or not rubric_raw:
            raise HTTPException(status_code=422, detail={"code": "CHALLENGE_RUBRIC_MISSING", "message": "Skill belum memiliki rubrik evaluasi versi-terkunci."})
        try:
            rubric = EvaluationRubric.model_validate(rubric_raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail={"code": "CHALLENGE_RUBRIC_INVALID", "message": "Rubrik Skill tidak memenuhi kontrak evaluator yang didukung."}) from exc

        if len(_canonical(challenge_input)) > MAX_JSON_BYTES or len(_canonical(expected_output)) > MAX_JSON_BYTES:
            raise HTTPException(status_code=413, detail={"code": "CHALLENGE_PAYLOAD_TOO_LARGE", "message": "Test case melebihi batas ukuran."})
        nonce = secrets.token_urlsafe(32)
        now = _now()
        evaluation_set = {"version": 1, "test_key": payload.test_key, "test_case": case}
        body = {
            "owner_user_id": owner_id, "agent_id": str(agent["id"]), "skill_id": str(skill["id"]),
            "agent_version": int(agent.get("version") or 1), "skill_version": int(skill["version"]),
            "skill_version_id": version_row.get("id") if version_row else None,
            "challenge_key": payload.test_key, "evaluation_set_version": 1,
            "evaluation_set_digest": _digest(evaluation_set),
            "rubric_key": rubric.rubric_key, "rubric_version": rubric.version,
            "rubric_digest": rubric.digest(), "evaluator_version": EVALUATOR_VERSION,
            "skill_snapshot": snapshot, "challenge_input": challenge_input, "expected_output": expected_output,
            "nonce_hash": hashlib.sha256(nonce.encode()).hexdigest(),
            "nonce_expires_at": (now + timedelta(seconds=NONCE_TTL_SECONDS)).isoformat(),
            "idempotency_key": payload.idempotency_key, "request_fingerprint": fingerprint,
            "status": "issued", "created_at": now.isoformat(), "updated_at": now.isoformat(),
        }
        rows = await store.request("POST", "agent_skill_challenge_runs", params={"select": "*"}, body=body, prefer="return=representation")
        if not rows:
            # A concurrent duplicate may have committed; reconcile by the unique owner/idempotency key.
            existing = await store.request("GET", "agent_skill_challenge_runs", params={
                "select": "*", "owner_user_id": f"eq.{owner_id}", "idempotency_key": f"eq.{payload.idempotency_key}", "limit": "1",
            })
            if not existing:
                raise HTTPException(status_code=503, detail={"code": "CHALLENGE_CREATE_UNCONFIRMED", "message": "Pembuatan challenge belum dapat dikonfirmasi."})
            if existing[0].get("request_fingerprint") != fingerprint:
                raise HTTPException(status_code=409, detail={"code": "CHALLENGE_IDEMPOTENCY_CONFLICT", "message": "Idempotency key sudah dipakai untuk challenge berbeda."})
            return {"run": _public_run(existing[0]), "nonce": nonce, "nonce_expires_at": body["nonce_expires_at"], "idempotent_replay": True}
        return {"run": _public_run(rows[0]), "nonce": nonce, "nonce_expires_at": body["nonce_expires_at"], "idempotent_replay": False}
    except HTTPException:
        raise
    except AgentRuntimePersistenceError as exc:
        raise _storage_error(exc) from exc


@router.post("/runs/{run_id}/submit")
async def submit_challenge(run_id: uuid.UUID, payload: ChallengeSubmit, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    submission = payload.submission
    try:
        submission_bytes = _canonical(submission)
        if len(submission_bytes) > MAX_JSON_BYTES:
            raise HTTPException(status_code=413, detail={"code": "CHALLENGE_SUBMISSION_TOO_LARGE", "message": "Jawaban melebihi batas ukuran."})
        fingerprint = hashlib.sha256(submission_bytes).hexdigest()
        row = await _get_run(store, owner_id, str(run_id))
        if not row:
            raise HTTPException(status_code=404, detail={"code": "CHALLENGE_RUN_NOT_FOUND", "message": "Challenge run tidak ditemukan."})
        if row["status"] in {"passed", "failed"}:
            if row.get("submission_fingerprint") != fingerprint:
                raise HTTPException(status_code=409, detail={"code": "CHALLENGE_REPLAY_CONFLICT", "message": "Challenge sudah diselesaikan dengan jawaban berbeda; replay ditolak."})
            return {"run": _public_run(row), "idempotent_replay": True, "achievement": await _achievement_for_run(store, owner_id, str(run_id)), "reward": {"status": "not_issued", "reason": "approved_reward_policy_required"}}
        if row["status"] != "issued":
            raise HTTPException(status_code=409, detail={"code": "CHALLENGE_NOT_SUBMITTABLE", "message": "Challenge tidak lagi dapat dikirim."})
        if _now() >= datetime.fromisoformat(row["nonce_expires_at"].replace("Z", "+00:00")):
            await store.request("PATCH", "agent_skill_challenge_runs", params={"id": f"eq.{run_id}", "owner_user_id": f"eq.{owner_id}", "status": "eq.issued"}, body={"status": "expired", "updated_at": _now().isoformat()})
            raise HTTPException(status_code=410, detail={"code": "CHALLENGE_NONCE_EXPIRED", "message": "Challenge telah kedaluwarsa; buat run baru."})
        if hashlib.sha256(payload.nonce.encode()).hexdigest() != row.get("nonce_hash"):
            raise HTTPException(status_code=403, detail={"code": "CHALLENGE_NONCE_INVALID", "message": "Nonce challenge tidak valid."})
        rubric_snapshot = row.get("skill_snapshot", {}).get("evaluation_rubric")
        rubric = EvaluationRubric.model_validate(rubric_snapshot)
        # The system derives task_success from the pinned expected output; the client cannot submit scores/signals.
        task_success = 1.0 if _canonical(submission) == _canonical(row["expected_output"]) else 0.0
        signals = {"task_success": CriterionSignal(score=task_success, evaluator_source="system")}
        result = evaluate_submission(rubric, signals)
        evidence = {
            "run_id": str(run_id), "submission_fingerprint": fingerprint,
            "expected_output_digest": _digest(row["expected_output"]), "evaluation": result.model_dump(mode="json"),
        }
        evidence_digest = _digest(evidence)
        updated = await store.request("PATCH", "agent_skill_challenge_runs", params={
            "id": f"eq.{run_id}", "owner_user_id": f"eq.{owner_id}", "status": "eq.issued",
            "nonce_hash": f"eq.{hashlib.sha256(payload.nonce.encode()).hexdigest()}",
        }, body={
            "status": "evaluating", "submission_fingerprint": fingerprint, "submission_payload": submission,
            "submitted_at": _now().isoformat(), "updated_at": _now().isoformat(),
        }, prefer="return=representation")
        if not updated:
            latest = await _get_run(store, owner_id, str(run_id))
            if latest and latest.get("submission_fingerprint") == fingerprint and latest.get("status") in {"evaluating", "passed", "failed"}:
                if latest.get("status") in {"passed", "failed"}:
                    return {"run": _public_run(latest), "idempotent_replay": True, "achievement": await _achievement_for_run(store, owner_id, str(run_id)), "reward": {"status": "not_issued", "reason": "approved_reward_policy_required"}}
                raise HTTPException(status_code=409, detail={"code": "CHALLENGE_EVALUATION_IN_PROGRESS", "message": "Pengiriman sudah diklaim dan sedang direkonsiliasi; tidak ada replay."})
            raise HTTPException(status_code=409, detail={"code": "CHALLENGE_ALREADY_CLAIMED", "message": "Nonce sudah digunakan atau challenge berubah."})
        final_status = "passed" if result.passed else "failed"
        final_rows = await store.request("PATCH", "agent_skill_challenge_runs", params={
            "id": f"eq.{run_id}", "owner_user_id": f"eq.{owner_id}", "status": "eq.evaluating",
            "submission_fingerprint": f"eq.{fingerprint}",
        }, body={
            "status": final_status, "evaluation_result": result.model_dump(mode="json"),
            "evidence_digest": evidence_digest, "completed_at": _now().isoformat(), "updated_at": _now().isoformat(),
        }, prefer="return=representation")
        if not final_rows:
            latest = await _get_run(store, owner_id, str(run_id))
            if not latest or latest.get("submission_fingerprint") != fingerprint or latest.get("status") not in {"passed", "failed"}:
                raise HTTPException(status_code=503, detail={"code": "CHALLENGE_FINALIZE_UNCONFIRMED", "message": "Hasil evaluasi belum dapat dikonfirmasi; jangan kirim ulang dengan nonce baru sebelum memuat ulang run."})
            final_rows = [latest]
        final = final_rows[0]
        achievement = None
        if final_status == "passed":
            achievement = await _award_evidence(store, owner_id, str(run_id), evidence_digest)
        return {"run": _public_run(final), "idempotent_replay": False, "achievement": achievement, "reward": {"status": "not_issued", "reason": "approved_reward_policy_required"}}
    except HTTPException:
        raise
    except AgentRuntimePersistenceError as exc:
        raise _storage_error(exc) from exc
    except Exception as exc:
        # Never expose expected outputs, snapshots or DB details in the public error contract.
        raise HTTPException(status_code=422, detail={"code": "CHALLENGE_EVALUATION_REJECTED", "message": "Challenge tidak dapat dievaluasi berdasarkan kontrak versi yang dipatok."}) from exc


async def _award_evidence(store: AgentRuntimeStore, owner_id: str, run_id: str, evidence_digest: str) -> dict[str, Any]:
    body = {"owner_user_id": owner_id, "challenge_run_id": run_id, "achievement_key": "skill_challenge_passed", "evidence_digest": evidence_digest}
    try:
        rows = await store.request("POST", "agent_skill_challenge_achievement_evidence", params={"select": "*"}, body=body, prefer="return=representation,resolution=ignore-duplicates")
        if rows:
            return {"key": "skill_challenge_passed", "status": "awarded", "evidence_digest": evidence_digest, "awarded_at": rows[0].get("awarded_at")}
    except AgentRuntimePersistenceError:
        pass
    existing = await store.request("GET", "agent_skill_challenge_achievement_evidence", params={
        "select": "achievement_key,evidence_digest,awarded_at", "owner_user_id": f"eq.{owner_id}",
        "challenge_run_id": f"eq.{run_id}", "achievement_key": "eq.skill_challenge_passed", "limit": "1",
    })
    if existing:
        if existing[0].get("evidence_digest") != evidence_digest:
            raise HTTPException(status_code=409, detail={"code": "ACHIEVEMENT_EVIDENCE_CONFLICT", "message": "Bukti achievement tidak konsisten."})
        return {"key": "skill_challenge_passed", "status": "awarded", "evidence_digest": evidence_digest, "awarded_at": existing[0].get("awarded_at")}
    raise HTTPException(status_code=503, detail={"code": "ACHIEVEMENT_WRITE_UNCONFIRMED", "message": "Bukti achievement belum dapat dikonfirmasi."})


async def _achievement_for_run(store: AgentRuntimeStore, owner_id: str, run_id: str) -> dict[str, Any] | None:
    rows = await store.request("GET", "agent_skill_challenge_achievement_evidence", params={
        "select": "achievement_key,evidence_digest,awarded_at", "owner_user_id": f"eq.{owner_id}",
        "challenge_run_id": f"eq.{run_id}", "limit": "1",
    })
    if not rows:
        return None
    item = rows[0]
    return {"key": item["achievement_key"], "status": "awarded", "evidence_digest": item["evidence_digest"], "awarded_at": item["awarded_at"]}


@router.get("/runs")
async def list_challenge_runs(limit: int = 30, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail={"code": "INVALID_LIMIT", "message": "Limit harus antara 1 dan 100."})
    try:
        store = _store()
        rows = await store.request("GET", "agent_skill_challenge_runs", params={
            "select": "*", "owner_user_id": f"eq.{user['id']}", "order": "created_at.desc", "limit": str(limit),
        })
        return {"items": [_public_run(row) for row in rows or []]}
    except AgentRuntimePersistenceError as exc:
        raise _storage_error(exc) from exc


@router.get("/runs/{run_id}")
async def get_challenge_run(run_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        store = _store()
        row = await _get_run(store, str(user["id"]), str(run_id))
        if not row:
            raise HTTPException(status_code=404, detail={"code": "CHALLENGE_RUN_NOT_FOUND", "message": "Challenge run tidak ditemukan."})
        return {"run": _public_run(row), "achievement": await _achievement_for_run(store, str(user["id"]), str(run_id))}
    except HTTPException:
        raise
    except AgentRuntimePersistenceError as exc:
        raise _storage_error(exc) from exc
