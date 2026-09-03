#!/usr/bin/env python3
"""The internal MCP tool from README 19.7: one tool, spawned per run by RuntimeService, never in the catalog."""
import asyncio
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.agent import Agent
from models.decision import DecisionRequest, DecisionStatus
from models.task import Task
from services.decision_service import create_decision_request

POLL_INTERVAL_SECONDS = 2.0

server = MCPServer(name="agent-office-ask-human")


@server.tool()
async def ask_human(question: str, options: list[str] | None = None, urgency: str = "normal") -> str:
    session_factory = build_session_factory()
    async with session_factory() as db:
        decision = await open_decision(db, question, options)
        return await wait_for_answer(db, decision.id)


def build_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    return async_sessionmaker(engine, expire_on_commit=False)


async def open_decision(db: AsyncSession, question: str, options: list[str] | None) -> DecisionRequest:
    agent = await db.get(Agent, uuid.UUID(os.environ["AGENT_ID"]))
    task = await load_task(db)
    formatted_options = format_options(options)
    return await create_decision_request(db, agent, task, question, formatted_options)


async def load_task(db: AsyncSession) -> Task | None:
    task_id = os.environ.get("TASK_ID")
    return await db.get(Task, uuid.UUID(task_id)) if task_id else None


def format_options(options: list[str] | None) -> list[dict] | None:
    if not options:
        return None
    return [{"id": str(index), "label": label} for index, label in enumerate(options)]


async def wait_for_answer(db: AsyncSession, decision_id: uuid.UUID) -> str:
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        db.expire_all()
        decision = await db.get(DecisionRequest, decision_id)
        if decision.status == DecisionStatus.ANSWERED:
            return decision.answer


if __name__ == "__main__":
    server.run(transport="stdio")
