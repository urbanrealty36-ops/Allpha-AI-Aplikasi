"""Provider-neutral, fail-closed cost guard for ENG-P09.

This module defines budget enforcement contracts only. It deliberately contains no
provider price table, currency conversion, default budget, or billing persistence.
All estimates and limits must come from an explicitly approved Model Router policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


class CostPolicyUnavailable(RuntimeError):
    """No approved budget policy or trusted estimate is available."""


class CostPolicyRejected(RuntimeError):
    """A request or provider result violates the approved cost policy."""


@dataclass(frozen=True)
class CostEstimate:
    provider_id: str
    model_id: str
    model_version: str
    usage_units: int
    cost_microunits: int

    def __post_init__(self) -> None:
        if not self.provider_id.strip() or not self.model_id.strip() or not self.model_version.strip():
            raise ValueError("cost estimate must identify provider and immutable model version")
        if self.usage_units < 0 or self.cost_microunits < 0:
            raise ValueError("cost estimate values must be non-negative")


@dataclass(frozen=True)
class CostBudget:
    sensitivity: str
    max_usage_units: int
    max_cost_microunits: int
    require_actual_cost: bool = True

    def __post_init__(self) -> None:
        if self.sensitivity not in {"public", "internal", "confidential", "restricted"}:
            raise ValueError("unsupported sensitivity for cost budget")
        if self.max_usage_units < 0 or self.max_cost_microunits < 0:
            raise ValueError("cost budget limits must be non-negative")


@dataclass(frozen=True)
class CostPolicyApproval:
    """Deployment-supplied reference to an explicitly approved policy decision.

    This is an attestation reference, not a mechanism to self-approve policy. The
    referenced review/ADR must exist outside this code and be verified by operators.
    """
    policy_id: str
    version: str
    approval_reference: str

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or not self.version.strip() or not self.approval_reference.strip():
            raise ValueError("cost policy approval must reference a policy, version and approval record")


@dataclass(frozen=True)
class CostAuthorization:
    sensitivity: str
    provider_id: str
    model_id: str
    model_version: str
    reserved_usage_units: int
    reserved_cost_microunits: int


def authorize_cost(
    *,
    sensitivity: str,
    estimate: CostEstimate | None,
    budgets: Mapping[str, CostBudget],
) -> CostAuthorization:
    """Authorize against explicit policy before provider execution; absence denies."""
    budget = budgets.get(sensitivity)
    if budget is None or budget.sensitivity != sensitivity:
        raise CostPolicyUnavailable("no approved cost budget for requested sensitivity")
    if estimate is None:
        raise CostPolicyUnavailable("no trusted cost estimate for selected provider/model")
    if estimate.usage_units > budget.max_usage_units:
        raise CostPolicyRejected("estimated usage exceeds approved request budget")
    if estimate.cost_microunits > budget.max_cost_microunits:
        raise CostPolicyRejected("estimated cost exceeds approved request budget")
    return CostAuthorization(
        sensitivity=sensitivity,
        provider_id=estimate.provider_id,
        model_id=estimate.model_id,
        model_version=estimate.model_version,
        reserved_usage_units=estimate.usage_units,
        reserved_cost_microunits=estimate.cost_microunits,
    )


def validate_actual_cost(
    *,
    authorization: CostAuthorization,
    actual_usage_units: int | None,
    actual_cost_microunits: int | None,
    budget: CostBudget,
) -> None:
    """Reject missing required attribution or usage/cost above the authorized cap."""
    if budget.sensitivity != authorization.sensitivity:
        raise CostPolicyRejected("cost budget sensitivity differs from authorization")
    if actual_usage_units is None or actual_cost_microunits is None:
        if budget.require_actual_cost:
            raise CostPolicyRejected("provider result lacks required usage/cost attribution")
        return
    if actual_usage_units < 0 or actual_cost_microunits < 0:
        raise CostPolicyRejected("actual usage/cost must be non-negative")
    if actual_usage_units > authorization.reserved_usage_units:
        raise CostPolicyRejected("actual usage exceeds reserved request budget")
    if actual_cost_microunits > authorization.reserved_cost_microunits:
        raise CostPolicyRejected("actual cost exceeds reserved request budget")
    if actual_usage_units > budget.max_usage_units or actual_cost_microunits > budget.max_cost_microunits:
        raise CostPolicyRejected("actual usage/cost exceeds approved budget")
