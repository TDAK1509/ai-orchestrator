"""A2.2: fastembed's all-MiniLM-L6-v2, ONNX, CPU. The first init downloads ~50MB from the model hub; after that it is local and offline, which is why prewarm_embedding_model runs once at startup instead of on the first user-facing call."""
import asyncio

from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model: TextEmbedding | None = None


async def prewarm_embedding_model() -> None:
    await asyncio.to_thread(get_model)


async def embed_text(text: str) -> list[float]:
    return (await embed_texts([text]))[0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return await asyncio.to_thread(embed_texts_sync, texts)


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    norm_a, norm_b = vector_norm(a), vector_norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product(a, b) / (norm_a * norm_b)


def embed_texts_sync(texts: list[str]) -> list[list[float]]:
    return [vector.tolist() for vector in get_model().embed(texts)]


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def vector_norm(vector: list[float]) -> float:
    return dot_product(vector, vector) ** 0.5


def dot_product(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
