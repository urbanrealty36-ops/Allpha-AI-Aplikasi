import pytest
from pydantic import ValidationError

from allpha_api.evaluation_engine import (
    EVALUATOR_VERSION,
    CriterionSignal,
    EvaluationContractError,
    EvaluationCriterion,
    EvaluationRubric,
    evaluate_submission,
)


def rubric(**changes):
    values = dict(
        rubric_key="skill-quality-v1",
        version=1,
        criteria=(
            EvaluationCriterion(key="task_success", weight=0.6, required=True, minimum_score=0.8),
            EvaluationCriterion(key="privacy_isolation", weight=0.4, required=True, minimum_score=1.0),
        ),
        pass_threshold=0.85,
    )
    values.update(changes)
    return EvaluationRubric(**values)


def test_evaluator_is_repeatable_and_pins_rubric_and_evaluator_version():
    contract = rubric()
    signals = {
        "task_success": CriterionSignal(score=0.9, evidence_ref="trace:abc"),
        "privacy_isolation": CriterionSignal(score=1.0, evidence_ref="test:privacy"),
    }
    first = evaluate_submission(contract, signals)
    second = evaluate_submission(contract, signals)
    assert first == second
    assert first.passed is True
    assert first.score == 0.94
    assert first.rubric_digest == contract.digest()
    assert first.evaluator_version == EVALUATOR_VERSION
    assert len(first.evidence_digest) == 64


def test_required_missing_signal_fails_closed_and_remains_traceable():
    result = evaluate_submission(rubric(), {"task_success": {"score": 1.0}})
    assert result.passed is False
    assert result.criterion_results["privacy_isolation"]["score"] is None


def test_required_criterion_below_minimum_fails_even_if_weighted_score_passes():
    contract = rubric(pass_threshold=0.5)
    result = evaluate_submission(contract, {
        "task_success": {"score": 1.0},
        "privacy_isolation": {"score": 0.5},
    })
    assert result.score == 0.8
    assert result.passed is False


def test_rejects_unknown_signal_and_signal_not_in_pinned_rubric():
    with pytest.raises(EvaluationContractError, match="unsupported signal"):
        evaluate_submission(rubric(), {"made_up_metric": {"score": 1.0}})
    with pytest.raises(EvaluationContractError, match="not in pinned rubric"):
        evaluate_submission(rubric(), {
            "task_success": {"score": 1.0},
            "privacy_isolation": {"score": 1.0},
            "factuality": {"score": 1.0},
        })


def test_rubric_weights_must_sum_to_one_and_criteria_must_be_unique():
    with pytest.raises(ValidationError, match="weights must sum to 1"):
        rubric(criteria=(
            EvaluationCriterion(key="task_success", weight=0.5),
            EvaluationCriterion(key="privacy_isolation", weight=0.4),
        ))
    with pytest.raises(ValidationError, match="unique"):
        rubric(criteria=(
            EvaluationCriterion(key="task_success", weight=0.5),
            EvaluationCriterion(key="task_success", weight=0.5),
        ))


def test_rejects_unsupported_evaluator_version_and_invalid_evidence_hash():
    with pytest.raises(ValidationError, match="unsupported evaluator version"):
        rubric(evaluator_version="latest")
    with pytest.raises(ValidationError, match="SHA-256"):
        CriterionSignal(score=1.0, evidence_ref="trace:abc", evidence_sha256="not-a-digest")


def test_reward_policy_is_not_part_of_evaluator_result():
    result = evaluate_submission(rubric(), {
        "task_success": {"score": 1.0},
        "privacy_isolation": {"score": 1.0},
    })
    assert "reward_amount" not in result.model_dump()
    assert "ledger_entry_id" not in result.model_dump()

def test_rejects_non_finite_scores():
    with pytest.raises(ValidationError):
        CriterionSignal(score=float("nan"))
    with pytest.raises(ValidationError):
        CriterionSignal(score=float("inf"))
