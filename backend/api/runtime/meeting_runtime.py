import asyncio
import json
import logging
import uuid
from pathlib import Path

from sqlalchemy import select

from models.agent import Agent
from models.meeting import (
    Meeting,
    MeetingAuthor,
    MeetingLoopState,
    MeetingStatus,
    MeetingTurn,
)
from models.session import AgentSession
from runtime.runtime_service import RuntimeService
from services import meeting_service
from services.context_builder import render_identity
from services.room_service import ensure_main_room

logger = logging.getLogger(__name__)

TURN_DEADLINE_SECONDS = 300.0
OUTCOME_SCHEMA_HINT = '{"summary": "...", "decisions": ["..."], "action_items": ["..."], "unresolved_questions": ["..."]}'

# allow-comment: one lock for every meeting, not one per meeting -- C5's own guard is "one meeting at a time", system-wide, matching the single _DIRECT_MERGE_LOCK task_service already uses for the same reason.
_MEETING_LOOP_LOCK = asyncio.Lock()
_ACTIVE_RUNS: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {}
_LOOP_TASKS: dict[uuid.UUID, asyncio.Task] = {}


def start_meeting_loop(runtime_service: RuntimeService, repo_root: Path, policy, meeting_id: uuid.UUID) -> None:
    """Fire-and-forget, same pattern as task_service.schedule_run_completion: the API route that triggers this must not block on a whole meeting."""
    if meeting_id in _LOOP_TASKS:
        return
    task = asyncio.create_task(run_meeting_loop(runtime_service, repo_root, policy, meeting_id))
    _LOOP_TASKS[meeting_id] = task
    task.add_done_callback(lambda _task: _LOOP_TASKS.pop(meeting_id, None))


async def run_meeting_loop(runtime_service: RuntimeService, repo_root: Path, policy, meeting_id: uuid.UUID) -> None:
    async with _MEETING_LOOP_LOCK:
        await mark_running(runtime_service, meeting_id)
        while await run_one_round_safely(runtime_service, repo_root, policy, meeting_id):
            pass


async def run_single_round(runtime_service: RuntimeService, repo_root: Path, policy, meeting_id: uuid.UUID) -> None:
    """A manual step, independent of loop_state -- used by the run-round API action to advance one turn without starting the automatic loop."""
    async with _MEETING_LOOP_LOCK:
        await run_one_round_safely(runtime_service, repo_root, policy, meeting_id, require_running=False)


async def force_close_out(runtime_service: RuntimeService, repo_root: Path, policy, meeting_id: uuid.UUID) -> None:
    async with _MEETING_LOOP_LOCK:
        await close_out_meeting(runtime_service, repo_root, policy, meeting_id)


async def mark_running(runtime_service: RuntimeService, meeting_id: uuid.UUID) -> None:
    async with runtime_service.session_factory() as db:
        meeting = await db.get(Meeting, meeting_id)
        await meeting_service.set_loop_state(db, meeting, MeetingLoopState.RUNNING)


async def run_one_round_safely(runtime_service, repo_root, policy, meeting_id, require_running: bool = True) -> bool:
    try:
        return await run_one_round(runtime_service, repo_root, policy, meeting_id, require_running)
    except Exception:
        logger.exception("meeting %s round failed", meeting_id)
        await pause_meeting(runtime_service, meeting_id)
        return False


async def run_one_round(runtime_service, repo_root, policy, meeting_id, require_running: bool) -> bool:
    async with runtime_service.session_factory() as db:
        meeting = await db.get(Meeting, meeting_id)
        if not can_advance(meeting, require_running):
            return False
        if meeting.current_round >= meeting.max_rounds:
            await close_out_meeting(runtime_service, repo_root, policy, meeting_id)
            return False
        speaker = await db.get(Agent, meeting.next_speaker_id)
    await run_turn(runtime_service, repo_root, meeting_id, speaker.id)
    return True


def can_advance(meeting: Meeting, require_running: bool) -> bool:
    if meeting.status != MeetingStatus.ACTIVE:
        return False
    return not require_running or meeting.loop_state == MeetingLoopState.RUNNING


async def pause_meeting(runtime_service: RuntimeService, meeting_id: uuid.UUID) -> None:
    async with runtime_service.session_factory() as db:
        meeting = await db.get(Meeting, meeting_id)
        if meeting is not None and meeting.status == MeetingStatus.ACTIVE:
            await meeting_service.set_loop_state(db, meeting, MeetingLoopState.PAUSED)


async def run_turn(runtime_service: RuntimeService, repo_root: Path, meeting_id: uuid.UUID, speaker_id: uuid.UUID) -> None:
    meeting, speaker, turn, prompt_text = await open_turn(runtime_service, meeting_id, speaker_id)
    run_id = await send_turn_prompt(runtime_service, repo_root, meeting, speaker, prompt_text)
    await record_turn_run(runtime_service, turn.id, run_id)
    content = await asyncio.wait_for(collect_turn_text(runtime_service, run_id), timeout=TURN_DEADLINE_SECONDS)
    await commit_turn_result(runtime_service, meeting_id, turn.id, speaker_id, content)


async def open_turn(runtime_service: RuntimeService, meeting_id: uuid.UUID, speaker_id: uuid.UUID) -> tuple:
    async with runtime_service.session_factory() as db:
        meeting = await db.get(Meeting, meeting_id)
        speaker = await db.get(Agent, speaker_id)
        participants = await meeting_service.list_participants_ordered(db, meeting_id)
        prompt_text = await build_turn_prompt(db, meeting, speaker, participants)
        turn = await meeting_service.open_meeting_turn(db, meeting_id, meeting.current_round, speaker_id)
        return meeting, speaker, turn, prompt_text


async def record_turn_run(runtime_service: RuntimeService, turn_id: uuid.UUID, run_id: uuid.UUID) -> None:
    async with runtime_service.session_factory() as db:
        turn = await db.get(MeetingTurn, turn_id)
        await meeting_service.set_turn_run(db, turn, run_id)


async def commit_turn_result(runtime_service: RuntimeService, meeting_id: uuid.UUID, turn_id: uuid.UUID, speaker_id: uuid.UUID, content: str) -> None:
    async with runtime_service.session_factory() as db:
        turn = await db.get(MeetingTurn, turn_id)
        await meeting_service.mark_turn_streamed(db, turn)
        meeting = await db.get(Meeting, meeting_id)
        participants = await meeting_service.list_participants_ordered(db, meeting_id)
        next_round, next_speaker_id = advance_pointer(meeting, participants, speaker_id)
        await meeting_service.commit_turn(db, meeting, turn, speaker_id, content, next_round, next_speaker_id)


def advance_pointer(meeting: Meeting, participants: list[Agent], speaker_id: uuid.UUID) -> tuple[int, uuid.UUID | None]:
    ids = [participant.id for participant in participants]
    index = ids.index(speaker_id)
    if index + 1 < len(ids):
        return meeting.current_round, ids[index + 1]
    return meeting.current_round + 1, ids[0]


async def build_turn_prompt(db, meeting: Meeting, speaker: Agent, participants: list[Agent]) -> str:
    transcript = await render_transcript(db, meeting.id, speaker.id, participants)
    parts = [
        f"Meeting topic: {meeting.topic}",
        f"Goal: {meeting.goal}" if meeting.goal else "",
        f"Facilitator instructions: {meeting.facilitator_instructions}" if meeting.facilitator_instructions else "",
        transcript,
        "It is your turn to speak. Give your contribution to the discussion in a few sentences.",
    ]
    return "\n\n".join(part for part in parts if part)


async def render_transcript(db, meeting_id: uuid.UUID, speaker_id: uuid.UUID, participants: list[Agent]) -> str:
    messages = await meeting_service.list_meeting_messages(db, meeting_id)
    relevant = messages_since_last_spoke(messages, speaker_id)
    if not relevant:
        return "No messages yet -- you may be opening the discussion."
    names = {participant.id: participant.name for participant in participants}
    lines = [format_transcript_line(message, names) for message in relevant]
    return "Transcript since you last spoke:\n" + "\n".join(lines)


def messages_since_last_spoke(messages: list, speaker_id: uuid.UUID) -> list:
    last_index = last_spoken_index(messages, speaker_id)
    return messages[last_index + 1 :] if last_index is not None else messages


def last_spoken_index(messages: list, speaker_id: uuid.UUID) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].agent_id == speaker_id:
            return index
    return None


def format_transcript_line(message, names: dict) -> str:
    speaker_label = "Human" if message.author == MeetingAuthor.HUMAN else names.get(message.agent_id, "Unknown")
    return f"- {speaker_label}: {message.content}"


async def send_turn_prompt(runtime_service: RuntimeService, repo_root: Path, meeting: Meeting, speaker: Agent, prompt_text: str) -> uuid.UUID:
    key = (meeting.id, speaker.id)
    run_id = _ACTIVE_RUNS.get(key)
    if run_id is not None:
        await runtime_service.send_message(run_id, build_follow_up_line(prompt_text))
        return run_id
    run_id = await spawn_or_resume_participant(runtime_service, repo_root, meeting, speaker, prompt_text)
    _ACTIVE_RUNS[key] = run_id
    return run_id


def build_follow_up_line(prompt_text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": prompt_text}}


async def spawn_or_resume_participant(runtime_service: RuntimeService, repo_root: Path, meeting: Meeting, speaker: Agent, prompt_text: str) -> uuid.UUID:
    agent_session = await find_meeting_session(runtime_service, meeting.id, speaker.id)
    if agent_session is not None and agent_session.claude_session_id:
        run = await runtime_service.resume_meeting_turn(speaker, agent_session, repo_root, [], prompt_text)
    else:
        run = await runtime_service.spawn_meeting_turn(speaker, meeting, repo_root, [], build_first_turn_message(speaker, meeting, prompt_text))
    return run.id


async def find_meeting_session(runtime_service: RuntimeService, meeting_id: uuid.UUID, agent_id: uuid.UUID) -> AgentSession | None:
    async with runtime_service.session_factory() as db:
        query = select(AgentSession).where(AgentSession.meeting_id == meeting_id, AgentSession.agent_id == agent_id)
        return (await db.execute(query)).scalars().first()


def build_first_turn_message(speaker: Agent, meeting: Meeting, prompt_text: str) -> dict:
    content = f"{render_identity(speaker)}\n\nYou are attending a meeting titled \"{meeting.topic}\".\n\n{prompt_text}"
    return {"type": "user", "message": {"role": "user", "content": content}}


async def collect_turn_text(runtime_service: RuntimeService, run_id: uuid.UUID) -> str:
    """C5 step 4: every text block from every assistant event, not just the last -- one event with only its first text block, or none at all when it also carries a tool_use block, would drop half of what an agent said."""
    parts = []
    async for event in runtime_service.read_turn_events(run_id):
        if event.kind in ("agent_message", "tool_use"):
            parts.extend(extract_text_blocks(event.raw))
    return "\n".join(parts).strip() or "(no response)"


def extract_text_blocks(payload: dict) -> list[str]:
    blocks = payload.get("message", {}).get("content", [])
    return [block.get("text", "") for block in blocks if block.get("type") == "text" and block.get("text")]


async def close_out_meeting(runtime_service: RuntimeService, repo_root: Path, policy, meeting_id: uuid.UUID) -> None:
    """C6: asks the persisted chair for the structured outcome, validated with one retry, then ends the meeting the same way a manual End Meeting does."""
    outcome = await request_outcome_with_retry(runtime_service, repo_root, meeting_id)
    await finish_meeting(runtime_service, repo_root, policy, meeting_id, outcome)
    await terminate_meeting_processes(runtime_service, meeting_id)


async def request_outcome_with_retry(runtime_service: RuntimeService, repo_root: Path, meeting_id: uuid.UUID) -> dict:
    outcome = await request_outcome(runtime_service, repo_root, meeting_id, strict=False)
    if outcome is not None:
        return outcome
    outcome = await request_outcome(runtime_service, repo_root, meeting_id, strict=True)
    return outcome or fallback_outcome()


async def request_outcome(runtime_service: RuntimeService, repo_root: Path, meeting_id: uuid.UUID, strict: bool) -> dict | None:
    async with runtime_service.session_factory() as db:
        meeting = await db.get(Meeting, meeting_id)
        chair = await db.get(Agent, meeting.chair_agent_id)
    run_id = await send_turn_prompt(runtime_service, repo_root, meeting, chair, build_outcome_prompt(strict))
    content = await asyncio.wait_for(collect_turn_text(runtime_service, run_id), timeout=TURN_DEADLINE_SECONDS)
    return parse_outcome_json(content)


def build_outcome_prompt(strict: bool) -> str:
    header = "The meeting is closing. As chair, summarize it." if not strict else "That reply could not be parsed. Reply with ONLY the JSON object below, no other text."
    return f"{header}\nReply with a JSON object matching this schema:\n{OUTCOME_SCHEMA_HINT}"


def parse_outcome_json(content: str) -> dict | None:
    """codex P2: a malformed list field (e.g. "decisions": "abc") must not reach extract_memories_from_meeting -- it iterates that field expecting a list of strings, and a bare string would yield one garbage memory per character."""
    parsed = extract_json_object(content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("summary"), str):
        return None
    return normalize_outcome(parsed)


def extract_json_object(content: str) -> object | None:
    try:
        candidate = content[content.index("{") : content.rindex("}") + 1]
        return json.loads(candidate)
    except (ValueError, json.JSONDecodeError):
        return None


def normalize_outcome(parsed: dict) -> dict:
    return {
        "summary": parsed["summary"],
        "decisions": as_string_list(parsed.get("decisions")),
        "action_items": as_string_list(parsed.get("action_items")),
        "unresolved_questions": as_string_list(parsed.get("unresolved_questions")),
    }


def as_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def fallback_outcome() -> dict:
    return {"summary": "The meeting ended without a structured outcome from the chair.", "decisions": [], "action_items": [], "unresolved_questions": []}


async def finish_meeting(runtime_service: RuntimeService, repo_root: Path, policy, meeting_id: uuid.UUID, outcome: dict) -> None:
    async with runtime_service.session_factory() as db:
        meeting = await db.get(Meeting, meeting_id)
        main_room = await ensure_main_room(db)
        await meeting_service.end_meeting(db, runtime_service, repo_root, policy, meeting, main_room, outcome["summary"], outcome.get("decisions"), outcome.get("action_items"), outcome.get("unresolved_questions"))


async def terminate_meeting_processes(runtime_service: RuntimeService, meeting_id: uuid.UUID) -> None:
    keys = [key for key in _ACTIVE_RUNS if key[0] == meeting_id]
    for key in keys:
        run_id = _ACTIVE_RUNS.pop(key)
        await runtime_service.kill_run(run_id)
        await runtime_service.finalize_meeting_run(run_id)
