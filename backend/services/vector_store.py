"""
Vector store service.

Goal: persist chunk embeddings (from embeddings.py) somewhere searchable,
and at query time, find which stored chunks are most similar to a new
query embedding. Chroma runs embedded — as a local Python library inside
this process — so there's no external service, API key, or network call
involved; everything is written to a local folder on disk.

Stages:
    1. Open the collection (once, cached)  -> get_collection()
    2. Store chunks + their embeddings      -> store_chunks()
    3. Query for similar chunks             -> query_similar()
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from chromadb import Collection

PERSIST_DIRECTORY = "chroma_data"
COLLECTION_NAME = "study_notes"


class HasChunkMetadata(Protocol):
    """Anything shaped like ingestion.py's Chunk can be stored — this is
    only used for type hints, keeping this file decoupled from ingestion.py
    the same way embeddings.py is."""

    text: str
    source: str
    page_number: int
    chunk_index: int


# =============================================================================
# STAGE 1: Open the collection (once, cached)
# =============================================================================


@lru_cache(maxsize=1)
def get_collection() -> "Collection":
    """Open (or create) the persistent Chroma collection and cache it.

    Like the embedding model in embeddings.py, opening the client/collection
    has some overhead, so this is done once per process and reused rather
    than reopened on every call. Data is written to PERSIST_DIRECTORY on
    disk, so it survives process restarts.
    """
    import chromadb  # imported lazily, mirroring embeddings.py's pattern

    client = chromadb.PersistentClient(path=PERSIST_DIRECTORY)
    return client.get_or_create_collection(name=COLLECTION_NAME)


# =============================================================================
# STAGE 2: Store chunks + their embeddings
# =============================================================================


def store_chunks(chunks: list[HasChunkMetadata], embeddings: list[list[float]]) -> None:
    """Add a batch of chunks and their pre-computed embeddings to the store.

    `chunks` and `embeddings` must be the same length and in the same
    order — this is exactly what ingestion.py's build_chunks() and
    embeddings.py's embed_chunks() naturally produce together.

    Uses upsert (not add) so re-ingesting the same document overwrites its
    existing chunks instead of erroring or creating duplicates. Each
    chunk's ID is derived from its source filename + chunk index, so the
    same chunk from the same file always maps to the same ID.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks and embeddings must be the same length "
            f"(got {len(chunks)} chunks, {len(embeddings)} embeddings)"
        )

    if not chunks:
        return

    collection = get_collection()

    ids = [f"{c.source}::{c.chunk_index}" for c in chunks]
    documents = [c.text for c in chunks]
    metadatas = [{"source": c.source, "page_number": c.page_number} for c in chunks]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


# =============================================================================
# STAGE 3: Query for similar chunks
# =============================================================================


def query_similar(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """Return the top_k stored chunks most similar to a query embedding.

    Each result is a dict with `text`, `source`, `page_number`, and
    `distance` (lower distance = more similar), ordered from most to
    least similar — ready for generation.py to build a prompt from.
    """
    collection = get_collection()

    if collection.count() == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
    )

    matches: list[dict] = []
    for text, metadata, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        matches.append(
            {
                "text": text,
                "source": metadata["source"],
                "page_number": metadata["page_number"],
                "distance": distance,
            }
        )

    return matches
