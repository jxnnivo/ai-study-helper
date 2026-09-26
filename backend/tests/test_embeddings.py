"""
test_embeddings.py — verify embeddings.py against the real sentence-transformers
model (not a stub). Run this on your own machine, since it needs to download
the model from Hugging Face the first time.

Usage:
    python tests/test_embeddings.py

What it checks:
    - The model loads and returns 384-dimensional vectors (matches EMBEDDING_DIM)
    - embed_chunks() returns one vector per chunk, in the same order
    - embed_query() returns a single flat vector, not a list of vectors
    - Repeated calls to get_model() reuse the same loaded model (no reload)
    - A REAL semantic check: two sentences about the same topic should be
      more similar (higher cosine similarity) than two unrelated sentences.
      This is the check that actually proves the embeddings are meaningful,
      not just "some numbers came back."
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # so `services` is importable

from services.embeddings import EMBEDDING_DIM, embed_chunks, embed_query, get_model


class FakeChunk:
    """Stand-in for ingestion.py's Chunk — embed_chunks() only needs a
    `.text` attribute, so a real PDF isn't required to test this file."""

    def __init__(self, text: str):
        self.text = text


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b)


def main() -> None:
    checks: list[tuple[str, bool]] = []

    print("Loading model (this downloads ~90MB the first time you run it)...")
    model = get_model()
    model_again = get_model()
    checks.append(
        (
            "get_model() returns the same cached instance on a second call",
            model is model_again,
        )
    )

    print("Embedding a batch of chunks...")
    chunks = [
        FakeChunk("Photosynthesis converts light energy into chemical energy."),
        FakeChunk("Newton's second law relates force, mass, and acceleration."),
        FakeChunk("The mitochondria is the powerhouse of the cell."),
    ]
    vectors = embed_chunks(chunks)

    checks.append(
        ("embed_chunks() returns one vector per chunk", len(vectors) == len(chunks))
    )
    checks.append(
        (
            f"Each vector is {EMBEDDING_DIM}-dimensional",
            all(len(v) == EMBEDDING_DIM for v in vectors),
        )
    )
    checks.append(("embed_chunks([]) returns an empty list", embed_chunks([]) == []))

    print("Embedding a single query...")
    query_vector = embed_query("What is photosynthesis?")
    checks.append(
        (
            f"embed_query() returns a single {EMBEDDING_DIM}-dim vector",
            len(query_vector) == EMBEDDING_DIM,
        )
    )

    try:
        embed_query("")
        checks.append(("embed_query('') raises ValueError", False))
    except ValueError:
        checks.append(("embed_query('') raises ValueError", True))

    print("Running the semantic similarity check...")
    photosynthesis_query = embed_query("How do plants make energy from sunlight?")
    photosynthesis_chunk = embed_query(
        "Photosynthesis converts light energy into chemical energy."
    )
    unrelated_chunk = embed_query(
        "Newton's second law relates force, mass, and acceleration."
    )

    sim_related = cosine_similarity(photosynthesis_query, photosynthesis_chunk)
    sim_unrelated = cosine_similarity(photosynthesis_query, unrelated_chunk)

    print(f"  similarity(query, related chunk)   = {sim_related:.3f}")
    print(f"  similarity(query, unrelated chunk) = {sim_unrelated:.3f}")

    checks.append(
        (
            "A related chunk scores higher similarity than an unrelated one "
            "(proves the embeddings capture meaning, not just word overlap)",
            sim_related > sim_unrelated,
        )
    )

    print("\nResults:")
    all_passed = True
    for description, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {description}")

    print(
        "\n"
        + ("All checks passed." if all_passed else "Some checks FAILED — see above.")
    )
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
