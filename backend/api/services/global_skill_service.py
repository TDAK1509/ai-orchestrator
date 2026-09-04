import json
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from db import commit
from models.skill import AgentSkillAssignment, Skill, SkillSource

logger = logging.getLogger(__name__)


@dataclass
class GlobalSkillFile:
    slug: str
    name: str
    description: str | None
    instructions: str
    repository_path: str


def global_skills_dir() -> Path:
    override = os.environ.get("AGENT_OFFICE_GLOBAL_SKILLS_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "skills"


async def sync_global_skills(db, directory: Path) -> None:
    """The startup mirror (README 15): a fresh checkout gets the catalog before the first spawn, since nothing else reads skills/ from disk."""
    scanned = scan_global_skills(directory)
    existing = await load_skills_by_slug(db)
    for skill_file in scanned:
        apply_scanned_skill(db, existing.get(skill_file.slug), skill_file)
    await delete_stale_global_skills(db, existing, {skill_file.slug for skill_file in scanned})
    await commit(db)


def scan_global_skills(directory: Path) -> list[GlobalSkillFile]:
    if not directory.is_dir():
        return []
    root = directory.resolve()
    candidates = (read_global_skill(root, entry) for entry in sorted(directory.iterdir()))
    return [skill for skill in candidates if skill is not None]


def read_global_skill(root: Path, entry: Path) -> GlobalSkillFile | None:
    skill_md = entry / "SKILL.md"
    if not is_contained_skill_directory(root, entry, skill_md):
        return None
    return build_global_skill_file(root, entry, skill_md)


def is_contained_skill_directory(root: Path, entry: Path, skill_md: Path) -> bool:
    """skills/ is repo-committed and trusted, but a symlinked SKILL.md there could otherwise read an arbitrary server file, persist it in the database, and inject it into an agent prompt."""
    if entry.is_symlink() or skill_md.is_symlink() or not entry.is_dir() or not skill_md.exists():
        return False
    return entry.resolve().is_relative_to(root) and skill_md.resolve().is_relative_to(root)


def build_global_skill_file(root: Path, entry: Path, skill_md: Path) -> GlobalSkillFile:
    metadata = read_metadata(root, entry / "metadata.json")
    slug = entry.name
    return GlobalSkillFile(
        slug=slug,
        name=metadata.get("name") or slug,
        description=metadata.get("description"),
        instructions=read_instructions(skill_md),
        repository_path=f"skills/{slug}",
    )


def read_metadata(root: Path, path: Path) -> dict:
    if path.is_symlink() or not path.exists() or not path.resolve().is_relative_to(root):
        return {}
    return json.loads(path.read_text())


def read_instructions(skill_md: Path) -> str:
    return skill_md.read_text() if skill_md.exists() else ""


async def load_skills_by_slug(db) -> dict[str, Skill]:
    return {skill.slug: skill for skill in (await db.execute(select(Skill))).scalars()}


def apply_scanned_skill(db, existing: Skill | None, skill_file: GlobalSkillFile) -> None:
    """A slug collision with a UI-created skill is logged and skipped, not raised: raising here runs inside the startup lifespan, before app.py's ValueError handler applies, and would stop the backend from serving at all."""
    if existing is None:
        db.add(build_global_skill(skill_file))
        return
    if existing.source != SkillSource.GLOBAL:
        logger.warning("skipping global skill %r: slug already used by a custom skill", skill_file.slug)
        return
    update_global_skill(existing, skill_file)


def build_global_skill(skill_file: GlobalSkillFile) -> Skill:
    return Skill(
        id=uuid.uuid4(),
        slug=skill_file.slug,
        name=skill_file.name,
        description=skill_file.description,
        repository_path=skill_file.repository_path,
        source=SkillSource.GLOBAL,
        instructions=skill_file.instructions,
    )


def update_global_skill(skill: Skill, skill_file: GlobalSkillFile) -> None:
    skill.name = skill_file.name
    skill.description = skill_file.description
    skill.repository_path = skill_file.repository_path
    skill.instructions = skill_file.instructions


async def delete_stale_global_skills(db, existing: dict[str, Skill], scanned_slugs: set[str]) -> None:
    """Never drops an assigned row (README 15): the directory can vanish, but the assignment is unrecoverable once dropped, so the row keeps serving its last-known instructions."""
    stale = [skill for slug, skill in existing.items() if skill.source == SkillSource.GLOBAL and slug not in scanned_slugs]
    if not stale:
        return
    assigned_ids = await load_assigned_skill_ids(db, [skill.id for skill in stale])
    for skill in stale:
        if skill.id not in assigned_ids:
            await db.delete(skill)


async def load_assigned_skill_ids(db, skill_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    query = select(AgentSkillAssignment.skill_id).where(AgentSkillAssignment.skill_id.in_(skill_ids)).distinct()
    return {row[0] for row in (await db.execute(query)).all()}
