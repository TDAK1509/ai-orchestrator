import json
import re
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select

from models.agent import Agent
from models.base import utcnow
from models.skill import AgentSkillAssignment, Skill
from runtime import worktree as worktree_ops

SKILLS_RELATIVE_DIR = ".agent-office/skills"


async def create_skill(db, config_worktree: Path, name: str, description: str | None, instructions: str) -> Skill:
    """Flushes before writing files: created_at is a Python-side default that only exists after the INSERT, and metadata.json needs the real value."""
    slug = require_nonempty_slug(name)
    skill = Skill(id=uuid.uuid4(), slug=slug, name=name, description=description, repository_path=f"{SKILLS_RELATIVE_DIR}/{slug}")
    db.add(skill)
    await db.flush()
    write_skill_files(skill_dir(config_worktree, slug), skill, instructions)
    await commit_skill_change(config_worktree, f'agent-office: add skill "{name}"')
    await db.commit()
    return skill


async def edit_skill(db, config_worktree: Path, skill: Skill, name: str | None = None, description: str | None = None, instructions: str | None = None) -> Skill:
    apply_skill_edits(skill, name, description)
    skill.updated_at = utcnow()
    await db.flush()
    path = skill_dir(config_worktree, skill.slug)
    write_skill_files(path, skill, resolve_instructions(path, instructions))
    await commit_skill_change(config_worktree, f'agent-office: update skill "{skill.name}"')
    await db.commit()
    return skill


def apply_skill_edits(skill: Skill, name: str | None, description: str | None) -> None:
    if name is not None:
        skill.name = name
    if description is not None:
        skill.description = description


def resolve_instructions(path: Path, instructions: str | None) -> str:
    return instructions if instructions is not None else read_instructions(path)


async def delete_skill(db, config_worktree: Path, skill: Skill) -> None:
    """DB changes are flushed (and so validated) before Git is touched: a failure here must not leave the catalog file gone while the row survives."""
    await delete_skill_assignments(db, skill.id)
    await db.delete(skill)
    await db.flush()
    remove_skill_files(skill_dir(config_worktree, skill.slug))
    await commit_skill_change(config_worktree, f'agent-office: remove skill "{skill.name}"')
    await db.commit()


async def delete_skill_assignments(db, skill_id: uuid.UUID) -> None:
    query = select(AgentSkillAssignment).where(AgentSkillAssignment.skill_id == skill_id)
    for assignment in (await db.execute(query)).scalars():
        await db.delete(assignment)


async def assign_skill(db, agent: Agent, skill: Skill) -> AgentSkillAssignment:
    assignment = AgentSkillAssignment(id=uuid.uuid4(), agent_id=agent.id, skill_id=skill.id)
    db.add(assignment)
    await db.commit()
    return assignment


async def unassign_skill(db, agent: Agent, skill: Skill) -> None:
    query = select(AgentSkillAssignment).where(AgentSkillAssignment.agent_id == agent.id, AgentSkillAssignment.skill_id == skill.id)
    assignment = (await db.execute(query)).scalars().first()
    if assignment is not None:
        await db.delete(assignment)
        await db.commit()


async def list_agent_skills(db, agent_id: uuid.UUID) -> list[Skill]:
    query = select(Skill).join(AgentSkillAssignment, AgentSkillAssignment.skill_id == Skill.id).where(AgentSkillAssignment.agent_id == agent_id)
    return list((await db.execute(query)).scalars())


async def list_assigned_agents(db, skill_id: uuid.UUID) -> list[Agent]:
    """Section 15: deleting a skill in use must show which agents are affected before confirmation."""
    query = select(Agent).join(AgentSkillAssignment, AgentSkillAssignment.agent_id == Agent.id).where(AgentSkillAssignment.skill_id == skill_id)
    return list((await db.execute(query)).scalars())


def skill_dir(config_worktree: Path, slug: str) -> Path:
    if not slug:
        raise ValueError("skill slug must not be empty: it would resolve to the catalog directory itself")
    return config_worktree / SKILLS_RELATIVE_DIR / slug


def write_skill_files(path: Path, skill: Skill, instructions: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(instructions)
    (path / "metadata.json").write_text(json.dumps(build_metadata(skill), indent=2))


def build_metadata(skill: Skill) -> dict:
    return {
        "id": str(skill.id),
        "slug": skill.slug,
        "name": skill.name,
        "description": skill.description,
        "createdAt": skill.created_at.isoformat(),
        "updatedAt": skill.updated_at.isoformat() if skill.updated_at else None,
    }


def remove_skill_files(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def read_instructions(path: Path) -> str:
    skill_md = path / "SKILL.md"
    return skill_md.read_text() if skill_md.exists() else ""


async def commit_skill_change(config_worktree: Path, message: str) -> str | None:
    return await worktree_ops.commit_paths(config_worktree, [SKILLS_RELATIVE_DIR], message)


def require_nonempty_slug(name: str) -> str:
    """A skill named entirely from punctuation/non-ASCII would slugify to "", and skill_dir("") is the catalog root itself: writing or, worse, deleting "that skill" would touch every skill."""
    slug = slugify(name)
    if not slug:
        raise ValueError(f"skill name {name!r} produces an empty slug; choose a name with at least one letter or digit")
    return slug


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
