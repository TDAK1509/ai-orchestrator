from fastapi import APIRouter, Depends

from deps import get_db
from serialization import serialize
from services.attention_service import list_unresolved_attention_events

router = APIRouter(prefix="/attention", tags=["attention"])


@router.get("")
async def list_unresolved_attention_route(db=Depends(get_db)):
    return [serialize(event) for event in await list_unresolved_attention_events(db)]
