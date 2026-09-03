#!/usr/bin/env python3
"""Read side of manual memory management (README 17.1/17.3), without a UI yet."""
import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import build_engine, build_session_factory
from services.memory_service import list_agent_memories, list_workspace_memories


async def main() -> None:
    args = parse_args()
    engine = build_engine()
    session_factory = build_session_factory(engine)
    async with session_factory() as db:
        records = await load_records(db, args)
        for record in records:
            print_record(record)
    await engine.dispose()


async def load_records(db, args: argparse.Namespace) -> list:
    if args.agent_id:
        return await list_agent_memories(db, uuid.UUID(args.agent_id))
    return await list_workspace_memories(db)


def print_record(record) -> None:
    pin = "*" if record.pinned else " "
    print(f"{pin} {record.id}  [{record.type.value}]  importance={record.importance}")
    print(f"    {record.content}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-id", default=None, help="omit to list workspace memory")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main())
