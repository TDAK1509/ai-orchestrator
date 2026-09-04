from sqlalchemy import select

from models.attention import AttentionEvent


async def list_unresolved_attention_events(db) -> list[AttentionEvent]:
    query = select(AttentionEvent).where(AttentionEvent.resolved.is_(False)).order_by(AttentionEvent.created_at)
    return list((await db.execute(query)).scalars())
