import re
import uuid

from sqlalchemy import select

from db import commit
from models.agent import Agent
from models.base import utcnow
from models.skill import AgentSkillAssignment, Skill, SkillSource


async def create_skill(db, name: str, description: str | None, instructions: str) -> Skill:
    slug = require_nonempty_slug(name)
    await require_free_slug(db, slug)
    skill = Skill(id=uuid.uuid4(), slug=slug, name=name, description=description, source=SkillSource.CUSTOM, instructions=instructions)
    db.add(skill)
    await commit(db)
    return skill


async def edit_skill(db, skill: Skill, name: str | None = None, description: str | None = None, instructions: str | None = None) -> Skill:
    require_custom_skill(skill)
    apply_skill_edits(skill, name, description, instructions)
    skill.updated_at = utcnow()
    await commit(db)
    return skill


def apply_skill_edits(skill: Skill, name: str | None, description: str | None, instructions: str | None) -> None:
    if name is not None:
        skill.name = name
    if description is not None:
        skill.description = description
    if instructions is not None:
        skill.instructions = instructions


async def delete_skill(db, skill: Skill) -> None:
    require_custom_skill(skill)
    await delete_skill_assignments(db, skill.id)
    await db.delete(skill)
    await commit(db)


async def delete_skill_assignments(db, skill_id: uuid.UUID) -> None:
    query = select(AgentSkillAssignment).where(AgentSkillAssignment.skill_id == skill_id)
    for assignment in (await db.execute(query)).scalars():
        await db.delete(assignment)


async def assign_skill(db, agent: Agent, skill: Skill) -> AgentSkillAssignment:
    assignment = AgentSkillAssignment(id=uuid.uuid4(), agent_id=agent.id, skill_id=skill.id)
    db.add(assignment)
    await commit(db)
    return assignment


async def unassign_skill(db, agent: Agent, skill: Skill) -> None:
    query = select(AgentSkillAssignment).where(AgentSkillAssignment.agent_id == agent.id, AgentSkillAssignment.skill_id == skill.id)
    assignment = (await db.execute(query)).scalars().first()
    if assignment is not None:
        await db.delete(assignment)
        await commit(db)


async def list_agent_skills(db, agent_id: uuid.UUID) -> list[Skill]:
    query = select(Skill).join(AgentSkillAssignment, AgentSkillAssignment.skill_id == Skill.id).where(AgentSkillAssignment.agent_id == agent_id)
    return list((await db.execute(query)).scalars())


async def list_assigned_agents(db, skill_id: uuid.UUID) -> list[Agent]:
    """Section 15: deleting a skill in use must show which agents are affected before confirmation."""
    query = select(Agent).join(AgentSkillAssignment, AgentSkillAssignment.agent_id == Agent.id).where(AgentSkillAssignment.skill_id == skill_id)
    return list((await db.execute(query)).scalars())


async def list_skills(db) -> list[Skill]:
    return list((await db.execute(select(Skill).order_by(Skill.name))).scalars())


async def require_free_slug(db, slug: str) -> None:
    query = select(Skill.id).where(Skill.slug == slug)
    if (await db.execute(query)).first() is not None:
        raise ValueError(f"a skill with slug {slug!r} already exists")


def require_custom_skill(skill: Skill) -> None:
    if skill.source != SkillSource.CUSTOM:
        raise ValueError(f"skill {skill.slug!r} is a global skill and cannot be edited or deleted from the UI")


def require_nonempty_slug(name: str) -> str:
    """A skill named entirely from punctuation/non-ASCII would slugify to "": reject it before it collides with every other empty-named skill."""
    slug = slugify(name)
    if not slug:
        raise ValueError(f"skill name {name!r} produces an empty slug; choose a name with at least one letter or digit")
    return slug


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
