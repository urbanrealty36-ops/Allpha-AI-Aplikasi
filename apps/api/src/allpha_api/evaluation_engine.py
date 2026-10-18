"""Versioned, deterministic evaluation contracts for ENG-P12.

This module scores trusted evaluator signals; it does not treat model output as
authority, call an LLM, issue rewards, or persist challenge records. Persistence,
authorization, and canonical reward-ledger integration belong to the API/data
slice and must use approved schema and financial policy.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EVALUATOR_VERSION = "allpha-evaluator-v1"
MAX_RUBRIC_BYTES = 16_384
MAX_SIGNALS = 32
MAX_EVIDENCE_BYTES = 8_192
_ALLOWED_CRITERIA = {
    "task_success",
    "relevance",
    "factuality",
    "citation_correctness",
    "retrieval_quality",
    "tool_success",
    "privacy_isolation",
    "prompt_injection_resilience",
    "workflow_determinism",
    "safety",
    "latency_budget",
    "cost_budget",
}
_SLUG = re.compile(r"^[a-z][a-z0-9_-]{2,59}$")


class EvaluationContractError(ValueError):
    """Rubric or evaluation evidence violates the versioned contract."""


class EvaluationCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_min_score(cls, value: Any) -> Any:
        """Accept the one documented legacy alias without relaxing strict validation."""
        if not isinstance(value, dict) or "min_score" not in value:
            return value
        if "minimum_score" in value:
            raise ValueError("use only one of min_score or minimum_score")
        normalized = dict(value)
        normalized["minimum_score"] = normalized.pop("min_score")
        return normalized

    key: str = Field(min_length=3, max_length=60)
    weight: float = Field(gt=0, le=1)
    required: bool = True
    minimum_score: float = Field(default=0.0, ge=0, le=1)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if value not in _ALLOWED_CRITERIA:
            raise ValueError("criterion key is not supported by the evaluation contract")
        return value


class EvaluationRubric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    rubric_key: str = Field(min_length=3, max_length=60)
    version: int = Field(ge=1, le=1_000_000)
    criteria: tuple[EvaluationCriterion, ...] = Field(min_length=1, max_length=MAX_SIGNALS)
    pass_threshold: float = Field(default=0.8, ge=0, le=1)
    evaluator_version: str = EVALUATOR_VERSION

    @field_validator("rubric_key")
    @classmethod
    def validate_rubric_key(cls, value: str) -> str:
        if not _SLUG.fullmatch(value):
            raise ValueError("rubric_key must be a lowercase slug")
        return value

    @field_validator("evaluator_version")
    @classmethod
    def validate_evaluator_version(cls, value: str) -> str:
        if value != EVALUATOR_VERSION:
            raise ValueError("unsupported evaluator version")
        return value

    @model_validator(mode="after")
    def validate_criteria(self) -> "EvaluationRubric":
        keys = [criterion.key for criterion in self.criteria]
        if len(keys) != len(set(keys)):
            raise ValueError("criterion keys must be unique")
        total = math.fsum(item.weight for item in self.criteria)
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError("criterion weights must sum to 1")
        return self

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class CriterionSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    score: float = Field(ge=0, le=1)
    evidence_ref: str | None = Field(default=None, max_length=256)
    evidence_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    evaluator_source: Literal["system", "human", "trusted_adapter"] = "system"

    @field_validator("evidence_sha256")
    @classmethod
    def validate_digest(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("evidence_sha256 must be a lowercase SHA-256 hex digest")
        return value

    @model_validator(mode="after")
    def evidence_reference_pair(self) -> "CriterionSignal":
        if self.evidence_sha256 and not self.evidence_ref:
            raise ValueError("evidence_ref is required when evidence_sha256 is supplied")
        return self


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    rubric_key: str
    rubric_version: int
    rubric_digest: str
    evaluator_version: str
    score: float = Field(ge=0, le=1)
    passed: bool
    criterion_results: dict[str, dict[str, Any]]
    evidence_digest: str


def evaluate_submission(
    rubric: EvaluationRubric,
    signals: dict[str, CriterionSignal | dict[str, Any]],
) -> EvaluationResult:
    """Score explicit, trusted criterion signals; missing required signals fail closed."""
    if len(signals) > MAX_SIGNALS:
        raise EvaluationContractError("too many criterion signals")

    parsed: dict[str, CriterionSignal] = {}
    for key, signal in signals.items():
        if key not in _ALLOWED_CRITERIA:
            raise EvaluationContractError(f"unsupported signal key: {key}")
        try:
            parsed[key] = signal if isinstance(signal, CriterionSignal) else CriterionSignal.model_validate(signal)
        except Exception as exc:
            raise EvaluationContractError(f"invalid signal for {key}") from exc

    rubric_keys = {criterion.key for criterion in rubric.criteria}
    unknown = set(parsed) - rubric_keys
    if unknown:
        raise EvaluationContractError("signal supplied for criterion not in pinned rubric")

    criteria_result: dict[str, dict[str, Any]] = {}
    weighted_total = 0.0
    missing_required = False
    evidence_items: list[dict[str, Any]] = []

    for criterion in rubric.criteria:
        signal = parsed.get(criterion.key)
        if signal is None:
            if criterion.required:
                missing_required = True
            criteria_result[criterion.key] = {
                "weight": criterion.weight,
                "required": criterion.required,
                "score": None,
                "passed": False if criterion.required else None,
                "evidence_ref": None,
                "evidence_sha256": None,
                "evaluator_source": None,
            }
            continue

        passed_criterion = signal.score >= criterion.minimum_score
        weighted_total += signal.score * criterion.weight
        criteria_result[criterion.key] = {
            "weight": criterion.weight,
            "required": criterion.required,
            "score": signal.score,
            "passed": passed_criterion,
            "evidence_ref": signal.evidence_ref,
            "evidence_sha256": signal.evidence_sha256,
            "evaluator_source": signal.evaluator_source,
        }
        evidence_items.append({
            "key": criterion.key,
            "score": signal.score,
            "evidence_ref": signal.evidence_ref,
            "evidence_sha256": signal.evidence_sha256,
            "evaluator_source": signal.evaluator_source,
        })

    evidence_json = json.dumps(
        evidence_items, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    if len(evidence_json) > MAX_EVIDENCE_BYTES:
        raise EvaluationContractError("evaluation evidence exceeds size limit")

    final_score = round(weighted_total, 6)
    required_failed = any(
        criterion.required
        and (
            criterion.key not in parsed
            or parsed[criterion.key].score < criterion.minimum_score
        )
        for criterion in rubric.criteria
    )
    passed = not missing_required and not required_failed and final_score >= rubric.pass_threshold

    return EvaluationResult(
        rubric_key=rubric.rubric_key,
        rubric_version=rubric.version,
        rubric_digest=rubric.digest(),
        evaluator_version=rubric.evaluator_version,
        score=final_score,
        passed=passed,
        criterion_results=criteria_result,
        evidence_digest=hashlib.sha256(evidence_json).hexdigest(),
    )
