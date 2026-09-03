#!/usr/bin/env python3
"""Delivers a human's answer back into the waiting ask_human tool call, per README 31.3."""
import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import build_engine, build_session_factory
from services.decision_service import answer_decision


async def main() -> None:
    args = parse_args()
    engine = build_engine()
    session_factory = build_session_factory(engine)
    async with session_factory() as db:
        decision = await answer_decision(db, uuid.UUID(args.decision_id), args.answer)
    print(f"answered {decision.id}: {decision.answer}")
    await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision-id", required=True)
    parser.add_argument("--answer", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main())
