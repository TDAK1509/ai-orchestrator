import json

from runtime.stream_parser import parse_stream_line


def test_parses_init_event_into_session_started():
    line = json.dumps({"type": "system", "subtype": "init", "session_id": "sess_1"})
    event = parse_stream_line(line)
    assert event.kind == "session_started"
    assert event.claude_session_id == "sess_1"


def test_parses_assistant_text_into_agent_message():
    payload = {"type": "assistant", "message": {"content": [{"type": "text", "text": "hello"}]}}
    event = parse_stream_line(json.dumps(payload))
    assert event.kind == "agent_message"
    assert event.text == "hello"


def test_parses_assistant_tool_use_into_tool_use_with_file_path():
    block = {"type": "tool_use", "name": "Write", "input": {"file_path": "src/token.ts"}}
    payload = {"type": "assistant", "message": {"content": [block]}}
    event = parse_stream_line(json.dumps(payload))
    assert event.kind == "tool_use"
    assert event.tool_name == "Write"
    assert event.file_path == "src/token.ts"


def test_parses_result_into_run_finished():
    payload = {"type": "result", "subtype": "success"}
    event = parse_stream_line(json.dumps(payload))
    assert event.kind == "run_finished"
    assert event.exit_result == "success"


def test_malformed_line_becomes_unknown_and_never_raises():
    event = parse_stream_line("not json")
    assert event.kind == "unknown"


def test_blank_line_becomes_unknown():
    event = parse_stream_line("   \n")
    assert event.kind == "unknown"
