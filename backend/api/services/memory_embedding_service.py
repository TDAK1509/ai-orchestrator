from sqlalchemy import or_, select

from db import commit
from models.memory import MemoryRecord
from services.embedding_service import MODEL_NAME, embed_texts

SWEEP_BATCH_SIZE = 32


async def sweep_missing_embeddings(db) -> int:
    """A2.3: selects embedding IS NULL or embedding_model <> current -- otherwise vectors from a retired model stay mixed with new ones forever and comparisons are meaningless."""
    total = 0
    while True:
        records = await find_unembedded_records(db)
        if not records:
            return total
        await embed_and_store(db, records)
        total += len(records)


async def find_unembedded_records(db) -> list[MemoryRecord]:
    query = (
        select(MemoryRecord)
        .where(or_(MemoryRecord.embedding.is_(None), MemoryRecord.embedding_model != MODEL_NAME))
        .limit(SWEEP_BATCH_SIZE)
    )
    return list((await db.execute(query)).scalars())


async def embed_and_store(db, records: list[MemoryRecord]) -> None:
    vectors = await embed_texts([record.content for record in records])
    for record, vector in zip(records, vectors, strict=True):
        record.embedding = vector
        record.embedding_model = MODEL_NAME
        record.embedding_dim = len(vector)
    await commit(db)
