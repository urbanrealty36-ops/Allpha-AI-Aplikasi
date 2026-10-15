import pytest

from allpha_api.cost_policy import (
    CostBudget,
    CostEstimate,
    CostPolicyRejected,
    CostPolicyUnavailable,
    authorize_cost,
    validate_actual_cost,
)


def budget(**changes):
    values = dict(sensitivity="internal", max_usage_units=1000, max_cost_microunits=50000)
    values.update(changes)
    return CostBudget(**values)


def estimate(**changes):
    values = dict(
        provider_id="approved-adapter",
        model_id="approved-model",
        model_version="immutable-v1",
        usage_units=100,
        cost_microunits=1200,
    )
    values.update(changes)
    return CostEstimate(**values)


def test_cost_policy_fails_closed_without_sensitivity_budget():
    with pytest.raises(CostPolicyUnavailable):
        authorize_cost(sensitivity="internal", estimate=estimate(), budgets={})


def test_cost_policy_fails_closed_without_trusted_estimate():
    with pytest.raises(CostPolicyUnavailable):
        authorize_cost(sensitivity="internal", estimate=None, budgets={"internal": budget()})


@pytest.mark.parametrize(
    "candidate",
    [
        estimate(usage_units=1001),
        estimate(cost_microunits=50001),
    ],
)
def test_cost_policy_rejects_estimate_over_budget(candidate):
    with pytest.raises(CostPolicyRejected):
        authorize_cost(sensitivity="internal", estimate=candidate, budgets={"internal": budget()})


def test_cost_policy_authorizes_only_explicit_route_and_budget():
    authorization = authorize_cost(
        sensitivity="internal",
        estimate=estimate(),
        budgets={"internal": budget()},
    )
    assert authorization.provider_id == "approved-adapter"
    assert authorization.model_version == "immutable-v1"
    assert authorization.reserved_cost_microunits == 1200


def test_actual_cost_must_be_attributed_when_policy_requires_it():
    authorization = authorize_cost(
        sensitivity="internal",
        estimate=estimate(),
        budgets={"internal": budget()},
    )
    with pytest.raises(CostPolicyRejected, match="attribution"):
        validate_actual_cost(
            authorization=authorization,
            actual_usage_units=None,
            actual_cost_microunits=None,
            budget=budget(),
        )


@pytest.mark.parametrize(
    ("usage", "cost"),
    [(101, 1200), (100, 1201)],
)
def test_actual_cost_cannot_exceed_reserved_amount(usage, cost):
    authorization = authorize_cost(
        sensitivity="internal",
        estimate=estimate(),
        budgets={"internal": budget()},
    )
    with pytest.raises(CostPolicyRejected):
        validate_actual_cost(
            authorization=authorization,
            actual_usage_units=usage,
            actual_cost_microunits=cost,
            budget=budget(),
        )


def test_optional_attribution_can_be_explicitly_allowed():
    permissive_budget = budget(require_actual_cost=False)
    authorization = authorize_cost(
        sensitivity="internal",
        estimate=estimate(),
        budgets={"internal": permissive_budget},
    )
    validate_actual_cost(
        authorization=authorization,
        actual_usage_units=None,
        actual_cost_microunits=None,
        budget=permissive_budget,
    )
