#!/usr/bin/env python3
"""Stands in for the real `claude` CLI in tests: same stream-json contract, no network."""
import json
import os
import sys
import time
import uuid


def main() -> None:
    session_id = resolve_session_id()
    prompt = read_initial_prompt()
    emit_init_event(session_id)
    emit_line({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Working on it."}]}})
    if os.environ.get("FAKE_CLAUDE_HANG"):
        time.sleep(3600)
    touched_path = write_marker_file(prompt)
    emit_tool_use_event(touched_path)
    emit_line({"type": "result", "subtype": os.environ.get("FAKE_CLAUDE_RESULT", "success")})
    sys.exit(int(os.environ.get("FAKE_CLAUDE_EXIT_CODE", "0")))


def resolve_session_id() -> str:
    args = sys.argv[1:]
    if "--resume" in args:
        return args[args.index("--resume") + 1]
    return os.environ.get("FAKE_CLAUDE_SESSION_ID") or str(uuid.uuid4())


def read_initial_prompt() -> dict:
    line = sys.stdin.readline()
    return json.loads(line) if line.strip() else {}


def emit_init_event(session_id: str) -> None:
    emit_line({"type": "system", "subtype": "init", "session_id": session_id})


def write_marker_file(prompt: dict) -> str:
    content = prompt.get("message", {}).get("content", "")
    path = os.path.join(os.getcwd(), "PROOF.md")
    with open(path, "a") as marker_file:
        marker_file.write(f"- {content}\n")
    return path


def emit_tool_use_event(touched_path: str) -> None:
    block = {"type": "tool_use", "name": "Write", "input": {"file_path": touched_path}}
    emit_line({"type": "assistant", "message": {"role": "assistant", "content": [block]}})


def emit_line(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
