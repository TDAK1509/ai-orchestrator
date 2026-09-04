#!/usr/bin/env python3
"""The operator-facing half of README 19.7: without a UI yet, this is how a human sees what's waiting on them."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import build_engine, build_session_factory
from models.agent import Agent
from models.decision import DecisionRequest
from models.task import Task
from services.decision_service import list_pending_decisions


async def main() -> None:
    engine = build_engine()
    session_factory = build_session_factory(engine)
    async with session_factory() as db:
        for decision in await list_pending_decisions(db):
            await print_decision(db, decision)
    await engine.dispose()


async def print_decision(db, decision: DecisionRequest) -> None:
    agent = await db.get(Agent, decision.agent_id)
    task = await db.get(Task, decision.task_id) if decision.task_id else None
    print(f"{decision.id}  {agent.name} ({task.title if task else 'no task'})")
    print(f"  {decision.question}")
    if decision.options:
        for option in decision.options:
            print(f"  - {option['label']}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
