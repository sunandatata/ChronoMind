import hashlib
import logging
import re
from functools import lru_cache

import numpy as np
from openai import AsyncOpenAI

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

VECTOR_SIZE = 1536
_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.+#-]*")


def has_openai_api_key() -> bool:
    key = settings.openai_api_key or ""
    return bool(key and not key.startswith("your_") and len(key) >= 20)


@lru_cache(maxsize=1)
def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


def local_embedding(text: str, dimensions: int = VECTOR_SIZE) -> list[float]:
    """
    Deterministic lexical embedding used when hosted embeddings are unavailable.

    It hashes unigrams and adjacent bigrams into a fixed-size signed feature vector,
    then L2-normalizes it. This is not a semantic model, but it is a real vector
    representation that supports meaningful lexical/technology-name retrieval and
    keeps Qdrant functional without placeholder vector shortcuts.
    """
    tokens = _tokenize(text)
    vector = np.zeros(dimensions, dtype=np.float32)

    if not tokens:
        return vector.tolist()

    features: list[tuple[str, float]] = [(token, 1.0) for token in tokens]
    features.extend(
        (f"{tokens[i]} {tokens[i + 1]}", 1.35)
        for i in range(len(tokens) - 1)
    )

    for feature, weight in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        hashed = int.from_bytes(digest, byteorder="big", signed=False)
        index = hashed % dimensions
        sign = 1.0 if (hashed >> 8) & 1 else -1.0
        vector[index] += sign * weight

    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector /= norm
    return vector.astype(float).tolist()


async def embed_text(text: str) -> list[float]:
    """Generate an embedding with OpenAI when configured, otherwise local hashing."""
    if has_openai_api_key():
        try:
            response = await _openai_client().embeddings.create(
                input=text,
                model="text-embedding-3-small",
                dimensions=VECTOR_SIZE,
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.warning("OpenAI embedding failed; using local embedding: %s", exc)

    return local_embedding(text)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    if not texts:
        return []

    if has_openai_api_key():
        try:
            response = await _openai_client().embeddings.create(
                input=texts,
                model="text-embedding-3-small",
                dimensions=VECTOR_SIZE,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            logger.warning("OpenAI batch embedding failed; using local embeddings: %s", exc)

    return [local_embedding(text) for text in texts]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b:
        return 0.0

    a_arr = np.array(a)
    b_arr = np.array(b)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))
