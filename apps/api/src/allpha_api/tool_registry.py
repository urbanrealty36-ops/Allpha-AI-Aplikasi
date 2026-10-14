"""Canonical, in-process registry for explicitly implemented low-risk Agent tools.

Only handlers registered here are executable. Registry metadata is descriptive; it
never grants an Agent permission or turns a Skill instruction into executable code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolDefinition:
    key: str
    version: str
    name: str
    description: str
    risk_level: str
    required_permission_scopes: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: ToolHandler

    def public_contract(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level,
            "required_permission_scopes": list(self.required_permission_scopes),
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "executable": True,
        }


def _normalize_text(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("text")
    if not isinstance(value, str):
        raise ValueError("text must be a string")
    if len(value) > 4000:
        raise ValueError("text must contain at most 4000 characters")
    return {"text": re.sub(r"\s+", " ", value).strip()}


_TEXT_NORMALIZE = ToolDefinition(
    key="text.normalize",
    version="1.0.0",
    name="Normalize text",
    description="Trim leading/trailing whitespace and collapse internal whitespace.",
    risk_level="low",
    required_permission_scopes=(),
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string", "maxLength": 4000}},
        "required": ["text"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
    handler=_normalize_text,
)

# This immutable mapping is the single in-process source of tool metadata and handlers.
_TOOL_REGISTRY: dict[str, ToolDefinition] = {_TEXT_NORMALIZE.key: _TEXT_NORMALIZE}


class UnknownToolError(ValueError):
    """Raised when a Skill refers to a tool with no registered handler."""


class ToolInputError(ValueError):
    """Raised when tool input does not satisfy the registered input contract."""


def list_tools() -> list[dict[str, Any]]:
    return [_TOOL_REGISTRY[key].public_contract() for key in sorted(_TOOL_REGISTRY)]


def get_tool(tool_key: str) -> ToolDefinition:
    tool = _TOOL_REGISTRY.get(tool_key)
    if tool is None:
        raise UnknownToolError(tool_key)
    return tool


def validate_tool_dependencies(dependencies: list[str]) -> None:
    if len(dependencies) != len(set(dependencies)):
        raise ValueError("tool_dependencies must not contain duplicates")
    unknown = sorted(set(dependencies) - _TOOL_REGISTRY.keys())
    if unknown:
        raise UnknownToolError(", ".join(unknown))


def execute_tool(tool_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    tool = get_tool(tool_key)
    if not isinstance(payload, dict):
        raise ToolInputError("tool input must be an object")
    unknown_fields = sorted(set(payload) - set(tool.input_schema["properties"]))
    if unknown_fields:
        raise ToolInputError(f"unexpected input field(s): {', '.join(unknown_fields)}")
    for field in tool.input_schema["required"]:
        if field not in payload:
            raise ToolInputError(f"missing required input field: {field}")
    try:
        return tool.handler(payload)
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc
