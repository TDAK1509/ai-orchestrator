#!/usr/bin/env python3
"""The other internal MCP tool from README 17.5/32.2: the agent produces the checkpoint itself, so extracting memory from it needs no separate model pass."""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from services.checkpoint_service import create_checkpoint

server = MCPServer(name="agent-office-checkpoint")


@server.tool()
async def write_checkpoint(summary: str, decisions: list[str] | None = None, discoveries: list[str] | None = None, important_files: list[str] | None = None, unfinished_work: list[str] | None = None, blockers: list[str] | None = None, risks: list[str] | None = None, branch: str | None = None, head_sha: str | None = None, test_status: str | None = None) -> str:
    fields = (summary, decisions, discoveries, important_files, unfinished_work, blockers, risks, branch, head_sha, test_status)
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        return await write_checkpoint_row(engine, *fields)
    finally:
        await engine.dispose()


async def write_checkpoint_row(engine, *fields) -> str:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        checkpoint = await save_checkpoint(db, *fields)
    return f"checkpoint {checkpoint.id} saved"


async def save_checkpoint(db, summary, decisions, discoveries, important_files, unfinished_work, blockers, risks, branch, head_sha, test_status):
    agent_id = uuid.UUID(os.environ["AGENT_ID"])
    task_id = uuid.UUID(os.environ["TASK_ID"]) if os.environ.get("TASK_ID") else None
    agent_session_id = uuid.UUID(os.environ["AGENT_SESSION_ID"])
    return await create_checkpoint(
        db, agent_id, agent_session_id, summary,
        task_id=task_id, decisions=decisions, discoveries=discoveries, important_files=important_files,
        unfinished_work=unfinished_work, blockers=blockers, risks=risks,
        branch=branch, head_sha=head_sha, test_status=test_status,
    )


if __name__ == "__main__":
    server.run(transport="stdio")
