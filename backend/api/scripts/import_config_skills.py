#!/usr/bin/env python3
"""One-off: backfills instructions for skills created before the catalog stopped reading SKILL.md from the agent-office/config worktree."""
import asyncio
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from db import build_engine, build_session_factory, commit
from models.skill import Skill, SkillSource


async def main() -> None:
    repo_root = Path(os.environ.get("AGENT_OFFICE_REPO_ROOT", "."))
    config_worktree = resolve_config_worktree(repo_root)
    engine = build_engine()
    session_factory = build_session_factory(engine)
    async with session_factory() as db:
        await backfill_instructions(db, config_worktree)
    await engine.dispose()


async def backfill_instructions(db, config_worktree: Path) -> None:
    """Leaves a row's `instructions` NULL, not "", when its SKILL.md can't be found: an empty string would read as "backfilled with nothing" and this script would never revisit it."""
    query = select(Skill).where(Skill.source == SkillSource.CUSTOM, Skill.instructions.is_(None))
    skills = list((await db.execute(query)).scalars())
    backfilled = [skill for skill in skills if apply_backfill(skill, config_worktree)]
    if backfilled:
        await commit(db)


def apply_backfill(skill: Skill, config_worktree: Path) -> bool:
    skill_md = config_worktree / ".agent-office" / "skills" / skill.slug / "SKILL.md"
    if not skill_md.exists():
        print(f"skipping {skill.slug}: no SKILL.md found at {skill_md}")
        return False
    skill.instructions = skill_md.read_text()
    print(f"backfilled {skill.slug}")
    return True


def resolve_config_worktree(repo_root: Path) -> Path:
    fingerprint = hashlib.sha256(str(repo_root.resolve()).encode()).hexdigest()[:12]
    return repo_root.parent / ".agent-office" / f"config-{fingerprint}"


if __name__ == "__main__":
    asyncio.run(main())
