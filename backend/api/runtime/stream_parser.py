import json
from dataclasses import dataclass, field
from typing import Any, Literal

DomainEventKind = Literal[
    "session_started",
    "agent_message",
    "tool_use",
    "tool_result",
    "run_finished",
    "unknown",
]


@dataclass
class DomainEvent:
    kind: DomainEventKind
    claude_session_id: str | None = None
    text: str | None = None
    tool_name: str | None = None
    file_path: str | None = None
    exit_result: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def parse_stream_line(line: str) -> DomainEvent:
    stripped = line.strip()
    if not stripped:
        return DomainEvent(kind="unknown", raw={})
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return DomainEvent(kind="unknown", raw={"raw_line": stripped})
    if not isinstance(payload, dict):
        return DomainEvent(kind="unknown", raw={"raw_line": stripped})
    return parse_stream_payload(payload)


def parse_stream_payload(payload: dict[str, Any]) -> DomainEvent:
    event_type = payload.get("type")
    if event_type == "system" and payload.get("subtype") == "init":
        return parse_init_event(payload)
    if event_type == "assistant":
        return parse_assistant_event(payload)
    if event_type == "user" and has_tool_result(payload):
        return parse_tool_result_event(payload)
    if event_type == "result":
        return parse_result_event(payload)
    return DomainEvent(kind="unknown", raw=payload)


def parse_init_event(payload: dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        kind="session_started",
        claude_session_id=payload.get("session_id"),
        raw=payload,
    )


def parse_assistant_event(payload: dict[str, Any]) -> DomainEvent:
    blocks = payload.get("message", {}).get("content", [])
    tool_use_block = find_block(blocks, "tool_use")
    if tool_use_block is not None:
        return build_tool_use_event(payload, tool_use_block)
    return build_agent_message_event(payload, blocks)


def build_tool_use_event(payload: dict[str, Any], tool_use_block: dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        kind="tool_use",
        tool_name=tool_use_block.get("name"),
        file_path=extract_file_path(tool_use_block),
        raw=payload,
    )


def build_agent_message_event(payload: dict[str, Any], blocks: list[dict[str, Any]]) -> DomainEvent:
    text_block = find_block(blocks, "text")
    return DomainEvent(
        kind="agent_message",
        text=text_block.get("text") if text_block else None,
        raw=payload,
    )


def find_block(blocks: list[dict[str, Any]], block_type: str) -> dict[str, Any] | None:
    return next((block for block in blocks if block.get("type") == block_type), None)


def extract_file_path(tool_use_block: dict[str, Any]) -> str | None:
    tool_input = tool_use_block.get("input", {})
    return tool_input.get("file_path") or tool_input.get("path")


def has_tool_result(payload: dict[str, Any]) -> bool:
    blocks = payload.get("message", {}).get("content", [])
    return find_block(blocks, "tool_result") is not None


def parse_tool_result_event(payload: dict[str, Any]) -> DomainEvent:
    return DomainEvent(kind="tool_result", raw=payload)


def parse_result_event(payload: dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        kind="run_finished",
        exit_result=payload.get("subtype", "success"),
        raw=payload,
    )
