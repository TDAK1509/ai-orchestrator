from pathlib import Path

from db import commit
from models.base import utcnow
from models.checkpoint import AgentCheckpoint
from models.session import AgentSession, ExecutionRun
from runtime.mcp_config import McpServerRef
from runtime.runtime_service import RuntimeService
from services.checkpoint_service import extract_memories_from_checkpoint
from services.context_builder import build_initial_message


async def rotate_session(db, runtime_service: RuntimeService, repo_root: Path, agent, task, task_worktree, old_agent_session: AgentSession, checkpoint: AgentCheckpoint, allowed_servers: list[McpServerRef]) -> ExecutionRun:
    """README 17.5: the agent and the worktree survive; only the conversation is replaced. The old session's checkpoint becomes memory first, so the new one starts with it already available through retrieval, not just the one-off summary in its first message."""
    await extract_memories_from_checkpoint(db, checkpoint)
    await archive_session(db, old_agent_session)
    message = await build_initial_message(db, agent, task, repo_root, allowed_servers, checkpoint)
    return await runtime_service.spawn(agent, task_worktree, allowed_servers, message)


async def archive_session(db, agent_session: AgentSession) -> None:
    agent_session.ended_at = utcnow()
    await commit(db)
