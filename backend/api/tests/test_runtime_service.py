import asyncio
import uuid

import pytest
from sqlalchemy import select

from models.agent import Agent
from models.attention import AttentionEvent
from models.base import utcnow
from models.session import AgentSession, BoundVia, ExecutionRun, RunStatus
from runtime.prompt import build_initial_user_message


async def test_spawn_persists_claude_session_id_from_first_event(runtime_service, agent, task_worktree):
    task, wt = task_worktree
    run = await runtime_service.spawn(agent, wt, [], build_initial_user_message(task))
    events = await drain(runtime_service.stream_events(run.id))
    assert any(event.kind == "session_started" for event in events)
    session = await runtime_service.db.get(AgentSession, run.agent_session_id)
    assert session.claude_session_id


async def test_spawn_records_head_commits_and_completes(runtime_service, agent, task_worktree):
    task, wt = task_worktree
    run = await runtime_service.spawn(agent, wt, [], build_initial_user_message(task))
    await drain(runtime_service.stream_events(run.id))
    assert run.before_head_commit
    assert run.after_head_commit
    assert run.status == RunStatus.COMPLETED
    assert run.exit_code == 0


async def test_spawn_surfaces_touched_files_as_tool_use_events(runtime_service, agent, task_worktree):
    task, wt = task_worktree
    run = await runtime_service.spawn(agent, wt, [], build_initial_user_message(task))
    events = await drain(runtime_service.stream_events(run.id))
    tool_events = [event for event in events if event.kind == "tool_use"]
    assert tool_events and tool_events[0].file_path.endswith("PROOF.md")


async def test_resume_reuses_the_same_claude_session_id(runtime_service, agent, task_worktree):
    task, wt = task_worktree
    first_run = await runtime_service.spawn(agent, wt, [], build_initial_user_message(task))
    await drain(runtime_service.stream_events(first_run.id))
    session = await runtime_service.db.get(AgentSession, first_run.agent_session_id)
    claude_session_id = session.claude_session_id

    second_run = await runtime_service.resume(agent, session, wt, [], "please continue")
    await drain(runtime_service.stream_events(second_run.id))

    assert second_run.bound_via == BoundVia.RESUME
    assert session.claude_session_id == claude_session_id


async def test_kill_run_stops_a_hanging_process(runtime_service, agent, task_worktree):
    task, wt = task_worktree
    message = build_initial_user_message(task)
    run = await runtime_service.spawn(agent, wt, [], message, env={"FAKE_CLAUDE_HANG": "1"})
    consumer = asyncio.create_task(drain(runtime_service.stream_events(run.id)))
    await asyncio.sleep(0.3)

    await runtime_service.kill_run(run.id)
    await asyncio.wait_for(consumer, timeout=5)

    assert run.status == RunStatus.KILLED


async def test_non_zero_exit_fails_the_run_even_if_the_stream_claims_success(runtime_service, agent, task_worktree):
    task, wt = task_worktree
    message = build_initial_user_message(task)
    run = await runtime_service.spawn(agent, wt, [], message, env={"FAKE_CLAUDE_EXIT_CODE": "1"})
    await drain(runtime_service.stream_events(run.id))

    assert run.exit_code == 1
    assert run.status == RunStatus.FAILED


async def test_resume_rejects_a_session_never_persisted_by_claude(runtime_service, agent, task_worktree):
    _task, wt = task_worktree
    session = AgentSession(id=uuid.uuid4(), agent_id=agent.id, task_worktree_id=wt.id, cwd=wt.path)
    runtime_service.db.add(session)
    await runtime_service.db.flush()

    with pytest.raises(ValueError):
        await runtime_service.resume(agent, session, wt, [], "continue")


async def test_resume_rejects_a_session_owned_by_another_agent(runtime_service, agent, task_worktree):
    _task, wt = task_worktree
    other_agent = Agent(id=uuid.uuid4(), name="Maya", role="Frontend Engineer", instructions="")
    session = AgentSession(
        id=uuid.uuid4(), agent_id=other_agent.id, task_worktree_id=wt.id, cwd=wt.path, claude_session_id="sess_1"
    )
    runtime_service.db.add_all([other_agent, session])
    await runtime_service.db.flush()

    with pytest.raises(ValueError):
        await runtime_service.resume(agent, session, wt, [], "continue")


async def test_reconcile_orphans_fails_runs_whose_pid_is_gone(runtime_service, agent, task_worktree):
    _task, wt = task_worktree
    orphan_session = AgentSession(id=uuid.uuid4(), agent_id=agent.id, task_worktree_id=wt.id, cwd=wt.path)
    orphan_run = ExecutionRun(
        id=uuid.uuid4(),
        agent_session_id=orphan_session.id,
        bound_via=BoundVia.SPAWN,
        status=RunStatus.RUNNING,
        pid=999999999,
        started_at=utcnow(),
    )
    runtime_service.db.add_all([orphan_session, orphan_run])
    await runtime_service.db.flush()

    reconciled = await runtime_service.reconcile_orphans()

    assert reconciled == [orphan_run]
    assert orphan_run.status == RunStatus.FAILED
    attention = await runtime_service.db.execute(select(AttentionEvent))
    assert attention.scalars().first() is not None


async def drain(events):
    collected = []
    async for event in events:
        collected.append(event)
    return collected
