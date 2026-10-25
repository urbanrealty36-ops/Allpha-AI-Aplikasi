"""Canonical ENG-P11 declarative workflow contracts and validation.

Definitions are data, never executable code. This module intentionally supports
only deterministic, no-side-effect node types in the first implementation slice.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkflowValidationError(ValueError):
    """Workflow definition is invalid or exceeds a safety bound."""


class WorkflowNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")
    kind: Literal["input", "constant", "pass_through", "concat", "merge", "agent_task"]
    config: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=5, ge=1, le=30)


class WorkflowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=80)


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    workflow_key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    version: int = Field(ge=1, le=2_147_483_647)
    nodes: list[WorkflowNode] = Field(min_length=1, max_length=50)
    edges: list[WorkflowEdge] = Field(default_factory=list, max_length=100)
    max_runtime_seconds: int = Field(default=60, ge=1, le=900)
    max_retries: int = Field(default=1, ge=0, le=3)

    @model_validator(mode="after")
    def validate_graph(self) -> "WorkflowDefinition":
        keys = [node.key for node in self.nodes]
        if len(keys) != len(set(keys)):
            raise ValueError("node keys must be unique")
        known = set(keys)
        adjacency: dict[str, list[str]] = defaultdict(list)
        indegree = {key: 0 for key in keys}
        edge_pairs: set[tuple[str, str]] = set()
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError("edge references an unknown node")
            if edge.source == edge.target:
                raise ValueError("self-loop edges are not allowed")
            pair = (edge.source, edge.target)
            if pair in edge_pairs:
                raise ValueError("duplicate edges are not allowed")
            edge_pairs.add(pair)
            adjacency[edge.source].append(edge.target)
            indegree[edge.target] += 1
        queue = deque(key for key in keys if indegree[key] == 0)
        visited = 0
        while queue:
            current = queue.popleft()
            visited += 1
            for target in adjacency[current]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        if visited != len(keys):
            raise ValueError("workflow graph must be acyclic")
        for node in self.nodes:
            _validate_json_object(node.config)
            if node.kind == "input" and not isinstance(node.config.get("field"), str):
                raise ValueError("input nodes require config.field")
            if node.kind == "constant" and "value" not in node.config:
                raise ValueError("constant nodes require config.value")
            if node.kind == "agent_task" and not isinstance(node.config.get("schedule_id"), str):
                raise ValueError("agent_task nodes require config.schedule_id")
            if node.kind == "concat" and node.config.get("separator", "") is not None and not isinstance(node.config.get("separator", ""), str):
                raise ValueError("concat separator must be a string")
        return self

    def topological_nodes(self) -> list[WorkflowNode]:
        by_key = {node.key: node for node in self.nodes}
        indegree = {node.key: 0 for node in self.nodes}
        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            adjacency[edge.source].append(edge.target)
            indegree[edge.target] += 1
        queue = deque(node.key for node in self.nodes if indegree[node.key] == 0)
        ordered: list[WorkflowNode] = []
        while queue:
            key = queue.popleft()
            ordered.append(by_key[key])
            for target in adjacency[key]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        return ordered

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _validate_json_object(value: dict[str, Any], *, max_bytes: int = 16_384) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("workflow config must be finite JSON data") from exc
    if len(encoded) > max_bytes:
        raise ValueError("workflow config exceeds 16 KiB")


def build_step_specs(definition: WorkflowDefinition) -> list[dict[str, Any]]:
    """Return immutable, deterministic initial step descriptors for the DB RPC."""
    return [
        {"node_key": node.key, "node_kind": node.kind, "node_config": node.config,
         "depends_on": [edge.source for edge in definition.edges if edge.target == node.key],
         "max_attempts": definition.max_retries + 1, "timeout_seconds": node.timeout_seconds}
        for node in definition.topological_nodes()
    ]


TERMINAL_RUN_STATES = frozenset({"succeeded", "failed", "cancelled", "timed_out"})
RUN_TRANSITIONS = {
    "created": frozenset({"queued", "cancelled"}),
    "queued": frozenset({"running", "cancelled", "failed"}),
    "running": frozenset({"succeeded", "failed", "cancelled", "timed_out"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "timed_out": frozenset(),
}


def validate_run_transition(current: str, target: str) -> None:
    if current not in RUN_TRANSITIONS or target not in RUN_TRANSITIONS[current]:
        raise WorkflowValidationError(f"invalid workflow run transition: {current} -> {target}")
