from fastapi import HTTPException


async def get_or_404(db, model, record_id, label: str):
    record = await db.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return record
