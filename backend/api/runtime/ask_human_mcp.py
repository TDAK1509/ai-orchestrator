#!/usr/bin/env python3
"""The internal MCP tool from README 19.7: one tool, spawned per run by RuntimeService, never in the catalog."""
import asyncio
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from internal_mcp_http import backend_api_base_url, backend_auth_headers
from mcp.server.mcpserver import MCPServer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.decision import DecisionRequest, DecisionStatus

POLL_INTERVAL_SECONDS = 2.0

server = MCPServer(name="agent-office-ask-human")


@server.tool()
async def ask_human(question: str, options: list[str] | None = None, urgency: str = "normal") -> str:
    """Each poll opens and closes its own short-lived session: the human may take minutes, and this must not hold one connection/transaction open the whole time."""
    decision_id = await open_decision(question, options)
    engine = create_async_engine(os.environ["DATABASE_URL"])
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        return await wait_for_answer(session_factory, decision_id)
    finally:
        await engine.dispose()


async def open_decision(question: str, options: list[str] | None) -> uuid.UUID:
    """POSTs to the backend process instead of writing the row directly (PR 1): create_decision_request's bus.publish must run where the WebSocket subscribers live, and that is the backend, not this subprocess."""
    body = build_decision_body(question, options)
    async with httpx.AsyncClient(base_url=backend_api_base_url(), headers=backend_auth_headers()) as client:
        response = await client.post("/decisions", json=body)
        response.raise_for_status()
        return uuid.UUID(response.json()["id"])


def build_decision_body(question: str, options: list[str] | None) -> dict:
    return {
        "agent_id": os.environ["AGENT_ID"],
        "agent_session_id": os.environ["AGENT_SESSION_ID"],
        "task_id": os.environ.get("TASK_ID"),
        "question": question,
        "options": format_options(options),
    }


def format_options(options: list[str] | None) -> list[dict] | None:
    if not options:
        return None
    return [{"id": str(index), "label": label} for index, label in enumerate(options)]


async def wait_for_answer(session_factory: async_sessionmaker[AsyncSession], decision_id: uuid.UUID) -> str:
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        async with session_factory() as db:
            decision = await db.get(DecisionRequest, decision_id)
            if decision.status == DecisionStatus.CANCELLED:
                raise RuntimeError("This decision was cancelled: the run it belonged to is no longer alive.")
            if decision.status == DecisionStatus.ANSWERED:
                return decision.answer


if __name__ == "__main__":
    server.run(transport="stdio")
