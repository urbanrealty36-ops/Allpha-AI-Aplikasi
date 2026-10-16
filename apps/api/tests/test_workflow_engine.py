import hashlib
import json

import pytest
from pydantic import ValidationError

from allpha_api.workflow_engine import (
    WorkflowDefinition, WorkflowValidationError, build_step_specs, validate_run_transition,
)


def definition(**overrides):
    body = {
        "workflow_key": "hello-world",
        "version": 1,
        "nodes": [
            {"key": "source", "kind": "input", "config": {"field": "name"}},
            {"key": "prefix", "kind": "constant", "config": {"value": "Hello "}},
            {"key": "message", "kind": "concat", "config": {"separator": ""}},
        ],
        "edges": [
            {"source": "source", "target": "message"},
            {"source": "prefix", "target": "message"},
        ],
    }
    body.update(overrides)
    return body


def test_definition_validates_dag_and_returns_deterministic_order():
    parsed = WorkflowDefinition.model_validate(definition())
    assert [node.key for node in parsed.topological_nodes()] == ["source", "prefix", "message"]
    specs = build_step_specs(parsed)
    assert specs[-1]["depends_on"] == ["source", "prefix"]
    assert all(spec["max_attempts"] == 2 for spec in specs)


def test_definition_digest_is_stable_for_semantically_identical_input():
    first = WorkflowDefinition.model_validate(definition())
    second = WorkflowDefinition.model_validate({**definition(), "nodes": list(reversed(definition()["nodes"]))})
    # Canonical JSON includes authoring order, so reordering nodes intentionally creates a different version digest.
    assert first.digest() != second.digest()
    assert len(first.digest()) == 64
    assert hashlib.sha256(first.canonical_json().encode()).hexdigest() == first.digest()


@pytest.mark.parametrize("edges", [
    [{"source": "source", "target": "source"}],
    [{"source": "source", "target": "missing"}],
    [{"source": "source", "target": "message"}, {"source": "source", "target": "message"}],
    [{"source": "source", "target": "message"}, {"source": "message", "target": "source"}],
])
def test_invalid_edges_are_rejected(edges):
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate({**definition(), "edges": edges})


def test_duplicate_node_keys_are_rejected():
    nodes = definition()["nodes"]
    with pytest.raises(ValidationError, match="node keys must be unique"):
        WorkflowDefinition.model_validate({**definition(), "nodes": nodes + [nodes[0]]})


@pytest.mark.parametrize("nodes", [
    [{"key": "only", "kind": "input", "config": {}}],
    [{"key": "only", "kind": "constant"}],
    [{"key": "only", "kind": "python", "config": {"code": "print(1)"}}],
])
def test_invalid_or_executable_node_contract_is_rejected(nodes):
    with pytest.raises((ValidationError, ValueError)):
        WorkflowDefinition.model_validate({**definition(), "nodes": nodes, "edges": []})


def test_definition_and_node_count_bounds_are_enforced():
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate({**definition(), "max_runtime_seconds": 901})
    many = [{"key": f"node-{i}", "kind": "constant", "config": {"value": i}} for i in range(51)]
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate({**definition(), "nodes": many, "edges": []})


def test_non_finite_config_is_rejected():
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate({**definition(), "nodes": [
            {"key": "const", "kind": "constant", "config": {"value": float("nan")}}], "edges": []})


@pytest.mark.parametrize("current,target", [
    ("created", "queued"), ("queued", "running"), ("running", "cancelled"),
    ("running", "succeeded"), ("running", "failed"),
])
def test_allowed_run_transitions(current, target):
    validate_run_transition(current, target)


@pytest.mark.parametrize("current,target", [
    ("succeeded", "running"), ("cancelled", "succeeded"), ("failed", "queued"),
    ("created", "succeeded"), ("running", "queued"),
])
def test_terminal_and_invalid_run_transitions_are_rejected(current, target):
    with pytest.raises(WorkflowValidationError):
        validate_run_transition(current, target)


def test_unknown_state_is_rejected():
    with pytest.raises(WorkflowValidationError):
        validate_run_transition("unknown", "running")
