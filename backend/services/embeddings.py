"""
Embeddings service.

Goal: turn chunk text (from ingestion.py) or a single query string into
numeric vectors using a local sentence-transformers model, so nothing has
to hit an external API just to embed text for the vector store. This keeps
embedding free and rate-limit-free; the Groq API is reserved for the
generation step later in the pipeline.

Stages:
    1. Load the model (once, cached)  -> get_model()
    2. Embed a batch of chunks         -> embed_chunks()
    3. Embed a single query            -> embed_query()
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class HasText(Protocol):
    """Anything with a `.text` attribute can be embedded — this is only
    used for type hints, so embed_chunks() isn't hard-coupled to
    ingestion.py's Chunk class specifically (decouple early, per the
    project's own convention)."""

    text: str


# =============================================================================
# STAGE 1: Load the model (once, cached)
# =============================================================================


@lru_cache(maxsize=1)
def get_model() -> "SentenceTransformer":
    """Load the sentence-transformers model and cache it for the life of
    the process.

    Loading the model reads its weights off disk (or downloads them on
    first use) and is slow — hundreds of milliseconds to a few seconds.
    That cost must be paid once per process, not once per request, so
    every call to embed_chunks()/embed_query() reuses the same loaded
    model instead of reloading it. lru_cache(maxsize=1) is a lightweight
    way to get that singleton behavior without writing a class for it.
    """
    from sentence_transformers import SentenceTransformer  # imported lazily

    return SentenceTransformer(MODEL_NAME)


# =============================================================================
# STAGE 2: Embed a batch of chunks (ingestion time)
# =============================================================================


def embed_chunks(chunks: list[HasText]) -> list[list[float]]:
    """Embed a batch of chunks all at once.

    Batch encoding is significantly faster than calling embed_query() in a
    loop, because the model processes multiple texts together instead of
    one at a time. Returns a list of embedding vectors in the same order
    as `chunks` — vectors[i] corresponds to chunks[i].
    """
    if not chunks:
        return []

    model = get_model()
    texts = [chunk.text for chunk in chunks]
    vectors = model.encode(texts, show_progress_bar=False)
    return vectors.tolist()


# =============================================================================
# STAGE 3: Embed a single query (query time)
# =============================================================================


def embed_query(query: str) -> list[float]:
    """Embed a single query string.

    Kept as a separate function (rather than reusing embed_chunks with a
    one-item list) because callers at query time have a plain string, not
    a Chunk, and want a single flat vector back, not a list containing one
    vector.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    model = get_model()
    vector = model.encode(query, show_progress_bar=False)
    return vector.tolist()
