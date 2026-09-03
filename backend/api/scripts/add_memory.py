#!/usr/bin/env python3
"""Manual memory management from README 17.1/17.3: without a UI yet, this is how a human adds workspace or per-agent memory."""
import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import build_engine, build_session_factory
from models.memory import MemoryScope, MemoryType
from services.memory_service import create_human_memory


async def main() -> None:
    args = parse_args()
    engine = build_engine()
    session_factory = build_session_factory(engine)
    async with session_factory() as db:
        record = await add_memory_from_args(db, args)
    print(f"created {record.id} (scope={record.scope.value})")
    await engine.dispose()


async def add_memory_from_args(db, args: argparse.Namespace):
    scope = MemoryScope.WORKSPACE if args.agent_id is None else MemoryScope.AGENT
    agent_id = uuid.UUID(args.agent_id) if args.agent_id else None
    return await create_human_memory(db, scope, args.content, MemoryType(args.type), agent_id=agent_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", required=True)
    parser.add_argument("--type", default="fact", choices=[t.value for t in MemoryType])
    parser.add_argument("--agent-id", default=None, help="omit for workspace-wide memory")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main())
