import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db
from events.bus import bus
from events.schema import SKILL_CREATED, SKILL_DELETED, SKILL_UPDATED
from lookups import get_or_404
from models.agent import Agent
from models.skill import Skill
from serialization import serialize
from services.skill_import_service import (
    ImportSummary,
    claude_code_skills_dir,
    import_claude_code_skills,
)
from services.skill_service import (
    assign_skill,
    create_skill,
    delete_skill,
    edit_skill,
    list_assigned_agents,
    list_skills,
    unassign_skill,
)

router = APIRouter(prefix="/skills", tags=["skills"])


class CreateSkillBody(BaseModel):
    name: str
    description: str | None = None
    instructions: str


class EditSkillBody(BaseModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None


@router.get("")
async def list_skills_route(db=Depends(get_db)):
    return [serialize(skill) for skill in await list_skills(db)]


@router.post("/import")
async def import_skills_route(db=Depends(get_db)):
    summary = await import_claude_code_skills(db, claude_code_skills_dir())
    publish_import_events(summary)
    return serialize_import_summary(summary)


def publish_import_events(summary: ImportSummary) -> None:
    """Other connected clients only learn about a create/edit through these events; a bulk import must raise the same ones a single create/edit would."""
    for skill in summary.created:
        bus.publish(SKILL_CREATED, serialize(skill))
    for skill in summary.updated:
        bus.publish(SKILL_UPDATED, serialize(skill))


def serialize_import_summary(summary: ImportSummary) -> dict:
    return {
        "created": [skill.slug for skill in summary.created],
        "updated": [skill.slug for skill in summary.updated],
        "skipped": summary.skipped,
        "errors": summary.errors,
    }


@router.get("/{skill_id}")
async def get_skill_route(skill_id: uuid.UUID, db=Depends(get_db)):
    skill = await get_or_404(db, Skill, skill_id, "skill")
    return serialize(skill)


@router.post("", status_code=201)
async def create_skill_route(body: CreateSkillBody, db=Depends(get_db)):
    skill = await create_skill(db, body.name, body.description, body.instructions)
    bus.publish(SKILL_CREATED, serialize(skill))
    return serialize(skill)


@router.patch("/{skill_id}")
async def edit_skill_route(skill_id: uuid.UUID, body: EditSkillBody, db=Depends(get_db)):
    skill = await get_or_404(db, Skill, skill_id, "skill")
    skill = await edit_skill(db, skill, body.name, body.description, body.instructions)
    bus.publish(SKILL_UPDATED, serialize(skill))
    return serialize(skill)


@router.get("/{skill_id}/agents")
async def list_skill_agents_route(skill_id: uuid.UUID, db=Depends(get_db)):
    await get_or_404(db, Skill, skill_id, "skill")
    return [serialize(agent) for agent in await list_assigned_agents(db, skill_id)]


@router.delete("/{skill_id}")
async def delete_skill_route(skill_id: uuid.UUID, db=Depends(get_db)):
    skill = await get_or_404(db, Skill, skill_id, "skill")
    payload = serialize(skill)
    await delete_skill(db, skill)
    bus.publish(SKILL_DELETED, payload)
    return {"deleted": True}


@router.post("/{skill_id}/assign/{agent_id}", status_code=201)
async def assign_skill_route(skill_id: uuid.UUID, agent_id: uuid.UUID, db=Depends(get_db)):
    skill, agent = await load_skill_and_agent(db, skill_id, agent_id)
    assignment = await assign_skill(db, agent, skill)
    return serialize(assignment)


@router.delete("/{skill_id}/assign/{agent_id}")
async def unassign_skill_route(skill_id: uuid.UUID, agent_id: uuid.UUID, db=Depends(get_db)):
    skill, agent = await load_skill_and_agent(db, skill_id, agent_id)
    await unassign_skill(db, agent, skill)
    return {"unassigned": True}


async def load_skill_and_agent(db, skill_id: uuid.UUID, agent_id: uuid.UUID):
    skill = await get_or_404(db, Skill, skill_id, "skill")
    agent = await get_or_404(db, Agent, agent_id, "agent")
    return skill, agent
