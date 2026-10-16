"""Authenticated FastAPI contracts for the canonical ENG-P11 Workflow Engine."""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from allpha_api.auth import current_user
from allpha_api.workflow_engine import WorkflowDefinition, WorkflowValidationError
from allpha_api.workflow_store import WorkflowPersistenceError, WorkflowStore

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])


class WorkflowDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: WorkflowDefinition


class WorkflowRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("input_payload")
    @classmethod
    def validate_input(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeEncodeError) as exc:
            raise ValueError("workflow input must be finite JSON data") from exc
        if len(encoded) > 16_384:
            raise ValueError("workflow input exceeds 16 KiB")
        return value


def _store() -> WorkflowStore:
    try:
        return WorkflowStore.from_environment()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={"code": "WORKFLOW_NOT_CONFIGURED",
            "message": "Penyimpanan Workflow Engine belum dikonfigurasi."}) from exc


def _storage_error(exc: WorkflowPersistenceError) -> HTTPException:
    return HTTPException(status_code=503, detail={"code": "WORKFLOW_STORAGE_UNAVAILABLE",
        "message": "Status penyimpanan workflow tidak dapat dipastikan."})


@router.post("/definitions", status_code=201)
async def create_definition(payload: WorkflowDefinitionCreate,
                            user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    definition = payload.definition
    try:
        canonical = definition.canonical_json()
        body = {"owner_user_id": str(user["id"]), "workflow_key": definition.workflow_key,
                "version": definition.version, "definition": json.loads(canonical),
                "digest": definition.digest(), "status": "active"}
        row = await _store().create_definition(body)
        return {"definition": row}
    except WorkflowPersistenceError as exc:
        raise _storage_error(exc) from exc


@router.get("/definitions")
async def list_definitions(limit: int = 50,
                           user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        return {"items": await _store().list_definitions(str(user["id"]), limit=limit)}
    except WorkflowPersistenceError as exc:
        raise _storage_error(exc) from exc


@router.post("/definitions/{definition_id}/runs", status_code=201)
async def create_run(definition_id: uuid.UUID, payload: WorkflowRunCreate, request: Request,
                     user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    try:
        definition = await store.get_definition(owner_id, str(definition_id))
        if not definition:
            raise HTTPException(status_code=404, detail={"code": "WORKFLOW_DEFINITION_NOT_FOUND",
                "message": "Definisi workflow tidak ditemukan."})
        parsed = WorkflowDefinition.model_validate(definition["definition"])
        if parsed.digest() != definition.get("digest"):
            raise HTTPException(status_code=409, detail={"code": "WORKFLOW_DEFINITION_DIGEST_MISMATCH",
                "message": "Digest definisi workflow tidak cocok."})
        trace_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        run = await store.create_run(owner_id, definition, payload.input_payload, trace_id)
        return {"run": run}
    except WorkflowPersistenceError as exc:
        raise _storage_error(exc) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=409, detail={"code": "WORKFLOW_DEFINITION_INVALID",
            "message": "Definisi workflow tersimpan tidak valid."}) from exc


@router.get("/runs")
async def list_runs(limit: int = 50,
                    user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        return {"items": await _store().list_runs(str(user["id"]), limit=limit)}
    except WorkflowPersistenceError as exc:
        raise _storage_error(exc) from exc


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        run = await _store().get_run(str(user["id"]), str(run_id))
    except WorkflowPersistenceError as exc:
        raise _storage_error(exc) from exc
    if not run:
        raise HTTPException(status_code=404, detail={"code": "WORKFLOW_RUN_NOT_FOUND",
            "message": "Workflow run tidak ditemukan."})
    return {"run": run}


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        row = await _store().cancel_run(str(user["id"]), str(run_id))
    except WorkflowPersistenceError as exc:
        raise _storage_error(exc) from exc
    if not row:
        raise HTTPException(status_code=404, detail={"code": "WORKFLOW_RUN_NOT_FOUND_OR_TERMINAL",
            "message": "Workflow run tidak ditemukan atau sudah terminal."})
    return {"run": row}
