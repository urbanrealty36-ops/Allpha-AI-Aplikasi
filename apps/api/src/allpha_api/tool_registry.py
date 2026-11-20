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
    execution_class: str
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
            "execution_class": self.execution_class,
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
    risk_level="low", execution_class="pure",
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

def _truncate_text(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload["text"]
    limit = payload["max_chars"]
    return {"text": text[:limit], "truncated": len(text) > limit}


def _split_text(payload: dict[str, Any]) -> dict[str, Any]:
    text, separator, max_parts = payload["text"], payload["separator"], payload["max_parts"]
    if separator == "":
        raise ValueError("separator must not be empty")
    return {"parts": text.split(separator, max_parts - 1)}


def _pick_json(payload: dict[str, Any]) -> dict[str, Any]:
    value: Any = payload["value"]
    path = payload["path"]
    if len(path) > 500:
        raise ValueError("path must contain at most 500 characters")
    for segment in path.split(".") if path else []:
        if isinstance(value, dict) and segment in value:
            value = value[segment]
        elif isinstance(value, list) and segment.isdigit() and int(segment) < len(value):
            value = value[int(segment)]
        else:
            return {"found": False, "value": None}
    return {"found": True, "value": value}


def _merge_json(payload: dict[str, Any]) -> dict[str, Any]:
    return {"value": {**payload["left"], **payload["right"]}}


_TEXT_TRUNCATE = ToolDefinition(
    key="text.truncate", version="1.0.0", name="Truncate text",
    description="Truncate text to an explicit maximum character count.",
    risk_level="low", execution_class="pure", required_permission_scopes=(),
    input_schema={"type":"object","properties":{
        "text":{"type":"string","maxLength":16000},
        "max_chars":{"type":"integer","minimum":1,"maximum":16000}},
        "required":["text","max_chars"],"additionalProperties":False},
    output_schema={"type":"object","properties":{
        "text":{"type":"string","maxLength":16000},"truncated":{"type":"boolean"}},
        "required":["text","truncated"],"additionalProperties":False},
    handler=_truncate_text,
)

_TEXT_SPLIT = ToolDefinition(
    key="text.split", version="1.0.0", name="Split text",
    description="Split text using a literal separator with a bounded number of parts.",
    risk_level="low", execution_class="pure", required_permission_scopes=(),
    input_schema={"type":"object","properties":{
        "text":{"type":"string","maxLength":16000},
        "separator":{"type":"string","minLength":1,"maxLength":100},
        "max_parts":{"type":"integer","minimum":1,"maximum":100}},
        "required":["text","separator","max_parts"],"additionalProperties":False},
    output_schema={"type":"object","properties":{
        "parts":{"type":"array","maxItems":100,"items":{"type":"string","maxLength":16000}}},
        "required":["parts"],"additionalProperties":False},
    handler=_split_text,
)

_JSON_PICK = ToolDefinition(
    key="json.pick", version="1.0.0", name="Pick JSON value",
    description="Read a nested object key or array index from caller-provided JSON without side effects.",
    risk_level="low", execution_class="pure", required_permission_scopes=(),
    input_schema={"type":"object","properties":{
        "value":{"type":"object","maxProperties":200},
        "path":{"type":"string","maxLength":500}},
        "required":["value","path"],"additionalProperties":False},
    output_schema={"type":"object","properties":{
        "found":{"type":"boolean"},"value":{}},
        "required":["found","value"],"additionalProperties":False},
    handler=_pick_json,
)

_JSON_MERGE = ToolDefinition(
    key="json.merge", version="1.0.0", name="Merge JSON objects",
    description="Shallow-merge two caller-provided JSON objects; right-hand keys take precedence.",
    risk_level="low", execution_class="pure", required_permission_scopes=(),
    input_schema={"type":"object","properties":{
        "left":{"type":"object","maxProperties":200},
        "right":{"type":"object","maxProperties":200}},
        "required":["left","right"],"additionalProperties":False},
    output_schema={"type":"object","properties":{
        "value":{"type":"object","maxProperties":400}},
        "required":["value"],"additionalProperties":False},
    handler=_merge_json,
)


def _validate_schema(value: Any, schema: dict[str, Any], path: str = "value", *, allow_missing_required: bool = False) -> None:
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected else []
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if types and not any(checks[t](value) for t in types if t in checks):
        raise ToolInputError(f"{path} has an invalid type")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        missing = sorted(set(schema.get("required", [])) - set(value))
        if missing and not allow_missing_required:
            raise ToolInputError(f"{path} missing required field(s): {', '.join(missing)}")
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise ToolInputError(f"{path} contains unexpected field(s): {', '.join(unknown)}")
        if len(value) > schema.get("maxProperties", 1000):
            raise ToolInputError(f"{path} exceeds maximum properties")
        for key, child in value.items():
            if key in properties:
                _validate_schema(child, properties[key], f"{path}.{key}", allow_missing_required=allow_missing_required)
    if isinstance(value, list):
        if len(value) > schema.get("maxItems", 1000):
            raise ToolInputError(f"{path} exceeds maximum items")
        if isinstance(schema.get("items"), dict):
            for index, child in enumerate(value):
                _validate_schema(child, schema["items"], f"{path}[{index}]", allow_missing_required=allow_missing_required)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 1000000):
            raise ToolInputError(f"{path} length is outside the allowed range")
        if "enum" in schema and value not in schema["enum"]:
            raise ToolInputError(f"{path} is not an allowed value")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", float("-inf")) or value > schema.get("maximum", float("inf")):
            raise ToolInputError(f"{path} is outside the allowed range")




def _social_approval_handler(_: dict[str, Any]) -> dict[str, Any]:
    raise ToolInputError("Social approvals execute only inside the lease-owning Agent Runtime worker")


_SOCIAL_COMMENT = ToolDefinition(
    key="social.comment", version="1.0.0", name="Publish approved Social comment",
    description="Execute an existing owner-approved comment against its pinned content target.",
    risk_level="high", execution_class="side_effecting", required_permission_scopes=(),
    input_schema={"type":"object","properties":{
        "approval_id":{"type":"string","minLength":36,"maxLength":36},
        "reason":{"type":"string","maxLength":500}},
        "required":["approval_id"],"additionalProperties":False},
    output_schema={"type":"object"}, handler=_social_approval_handler,
)
_SOCIAL_REPLY = ToolDefinition(
    key="social.reply", version="1.0.0", name="Publish approved Social reply",
    description="Execute an existing owner-approved reply against its pinned content and comment target.",
    risk_level="high", execution_class="side_effecting", required_permission_scopes=(),
    input_schema=_SOCIAL_COMMENT.input_schema, output_schema={"type":"object"},
    handler=_social_approval_handler,
)
_SOCIAL_STORY_REPLY = ToolDefinition(
    key="social.story_reply", version="1.0.0", name="Send approved Story reply",
    description="Execute an existing owner-approved Story reply through the canonical conversation lifecycle.",
    risk_level="high", execution_class="side_effecting", required_permission_scopes=(),
    input_schema=_SOCIAL_COMMENT.input_schema, output_schema={"type":"object"},
    handler=_social_approval_handler,
)
\n\n# This immutable mapping is the single in-process source of tool metadata and handlers.
_TOOL_REGISTRY: dict[str, ToolDefinition] = {tool.key: tool for tool in (_TEXT_NORMALIZE, _TEXT_TRUNCATE, _TEXT_SPLIT, _JSON_PICK, _JSON_MERGE, _SOCIAL_COMMENT, _SOCIAL_REPLY, _SOCIAL_STORY_REPLY)}


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


def validate_tool_input_partial(tool_key: str, payload: dict[str, Any]) -> None:
    """Validate supplied fields without requiring fields that a plan binding fills later."""
    tool = get_tool(tool_key)
    if not isinstance(payload, dict):
        raise ToolInputError("tool input must be an object")
    _validate_schema(payload, tool.input_schema, "input", allow_missing_required=True)


def validate_tool_input(tool_key: str, payload: dict[str, Any]) -> None:
    """Validate a complete registered tool input before scheduling execution."""
    tool = get_tool(tool_key)
    if not isinstance(payload, dict):
        raise ToolInputError("tool input must be an object")
    _validate_schema(payload, tool.input_schema, "input")


def execute_tool(tool_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    tool = get_tool(tool_key)
    if not isinstance(payload, dict):
        raise ToolInputError("tool input must be an object")
    try:
        _validate_schema(payload, tool.input_schema, "input")
        result = tool.handler(payload)
        if not isinstance(result, dict):
            raise ToolInputError("tool handler must return an object")
        _validate_schema(result, tool.output_schema, "output")
        return result
    except ToolInputError:
        raise
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc
