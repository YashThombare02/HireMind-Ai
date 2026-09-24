"""Sentence-Transformers embedding, lazily loaded once per process (the
model is ~90MB — loading it at import time would slow down every process
start, including tests that never touch this module).
"""

from functools import lru_cache

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed(text: str) -> list[float]:
    model = _get_model()
    vector = model.encode(text or "", normalize_embeddings=True)
    return vector.tolist()
