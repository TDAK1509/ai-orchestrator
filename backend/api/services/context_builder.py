from pathlib import Path

from models.agent import Agent
from models.task import Task
from runtime.mcp_config import McpServerRef
from services.config_repo_service import ensure_config_worktree
from services.memory_service import retrieve_context_memories
from services.skill_service import list_agent_skills, read_instructions, skill_dir


async def build_initial_message(db, agent: Agent, task: Task, repo_root: Path, allowed_servers: list[McpServerRef]) -> dict:
    """Combines identity + skills + MCP + memory + task (README 17.4/32.3): the CLI has no channel for this but the first user turn."""
    sections = [
        render_identity(agent),
        await render_skills(db, agent, repo_root),
        render_mcp_capabilities(allowed_servers),
        await render_memory(db, agent, task),
        render_task(task),
    ]
    content = "\n\n".join(section for section in sections if section)
    return {"type": "user", "message": {"role": "user", "content": content}}


def render_identity(agent: Agent) -> str:
    identity = f"You are {agent.name}, {agent.role}."
    return f"{identity}\n{agent.instructions}" if agent.instructions else identity


async def render_skills(db, agent: Agent, repo_root: Path) -> str:
    """File contents, not summaries (README 32.3): the assigned skill's actual SKILL.md, read from the catalog worktree."""
    skills = await list_agent_skills(db, agent.id)
    if not skills:
        return ""
    config_worktree = await ensure_config_worktree(repo_root)
    blocks = (f"## Skill: {skill.name}\n{read_instructions(skill_dir(config_worktree, skill.slug))}" for skill in skills)
    return "\n\n".join(blocks)


def render_mcp_capabilities(allowed_servers: list[McpServerRef]) -> str:
    if not allowed_servers:
        return ""
    return f"Available MCP servers: {', '.join(server.name for server in allowed_servers)}."


async def render_memory(db, agent: Agent, task: Task) -> str:
    memories = await retrieve_context_memories(db, agent.id, build_query_text(task))
    if not memories:
        return ""
    return "## Relevant memory\n" + "\n".join(f"- {memory.content}" for memory in memories)


def build_query_text(task: Task) -> str:
    return f"{task.title} {task.description or ''}"


def render_task(task: Task) -> str:
    return f"## Task\n{task.title}\n\n{task.description}" if task.description else f"## Task\n{task.title}"
