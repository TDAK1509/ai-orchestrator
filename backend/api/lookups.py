from fastapi import HTTPException


async def get_active_or_404(db, model, record_id, label: str):
    """Same as get_or_404, but an archived/inactive row (e.g. a Team) 404s too -- it exists, but nothing new should attach to it."""
    record = await get_or_404(db, model, record_id, label)
    if not record.active:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return record


async def get_or_404(db, model, record_id, label: str):
    record = await db.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return record
