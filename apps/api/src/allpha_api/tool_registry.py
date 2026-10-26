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


def validate_tool_input(tool_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a bounded JSON object against the registered Tool input contract without executing it."""
    tool = get_tool(tool_key)
    if not isinstance(payload, dict):
        raise ToolInputError("tool input must be an object")
    schema = tool.input_schema
    properties = schema.get("properties", {})
    unknown_fields = sorted(set(payload) - set(properties))
    if unknown_fields and schema.get("additionalProperties") is False:
        raise ToolInputError(f"unexpected input field(s): {', '.join(unknown_fields)}")
    for field in schema.get("required", []):
        if field not in payload:
            raise ToolInputError(f"missing required input field: {field}")
    type_checks = {
        "string": lambda value: isinstance(value, str),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": lambda value: isinstance(value, bool),
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
    }
    for field, value in payload.items():
        spec = properties.get(field)
        if not isinstance(spec, dict):
            continue
        expected_type = spec.get("type")
        checker = type_checks.get(expected_type)
        if checker and not checker(value):
            raise ToolInputError(f"{field} must be {expected_type}")
        if isinstance(value, str):
            if "maxLength" in spec and len(value) > int(spec["maxLength"]):
                raise ToolInputError(f"{field} must contain at most {spec['maxLength']} characters")
            if "minLength" in spec and len(value) < int(spec["minLength"]):
                raise ToolInputError(f"{field} must contain at least {spec['minLength']} characters")
        if "enum" in spec and value not in spec["enum"]:
            raise ToolInputError(f"{field} must be one of the allowed values")
    return payload


def execute_tool(tool_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    validate_tool_input(tool_key, payload)
    tool = get_tool(tool_key)
    try:
        return tool.handler(payload)
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc
