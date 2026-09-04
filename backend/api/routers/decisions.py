import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db
from serialization import serialize
from services.decision_service import answer_decision, list_pending_decisions

router = APIRouter(prefix="/decisions", tags=["decisions"])


class AnswerDecisionBody(BaseModel):
    answer: str


@router.get("")
async def list_pending_decisions_route(db=Depends(get_db)):
    return [serialize(decision) for decision in await list_pending_decisions(db)]


@router.post("/{decision_id}/answer")
async def answer_decision_route(decision_id: uuid.UUID, body: AnswerDecisionBody, db=Depends(get_db)):
    decision = await answer_decision(db, decision_id, body.answer)
    return serialize(decision)
