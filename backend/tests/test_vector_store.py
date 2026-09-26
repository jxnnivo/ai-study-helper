"""
test_vector_store.py — verify vector_store.py's storage and similarity search.

Unlike embeddings.py, this needs no external download or network access —
Chroma is a purely local, embedded library — so this runs entirely offline
and should behave identically for you as it did in development.

Usage:
    python tests/test_vector_store.py

Note: this deletes and recreates a test-only Chroma directory
(tests/fixtures/chroma_test_data) each run, so it never touches your real
chroma_data/ used by the actual app.
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # so `services` is importable

TEST_PERSIST_DIR = Path(__file__).parent / "fixtures" / "chroma_test_data"

# Point vector_store.py at a throwaway test directory before importing it,
# so this script never touches the real chroma_data/ the app actually uses.
import services.vector_store as vector_store  # noqa: E402

vector_store.PERSIST_DIRECTORY = str(TEST_PERSIST_DIR)


class FakeChunk:
    """Stand-in for ingestion.py's Chunk — store_chunks() only needs these
    four attributes, so a real PDF isn't required to test this file."""

    def __init__(self, text: str, source: str, page_number: int, chunk_index: int):
        self.text = text
        self.source = source
        self.page_number = page_number
        self.chunk_index = chunk_index


def main() -> None:
    checks: list[tuple[str, bool]] = []

    # Start from a clean slate every run.
    shutil.rmtree(TEST_PERSIST_DIR, ignore_errors=True)

    print("Checking an empty collection...")
    empty_results = vector_store.query_similar([1.0, 0.0, 0.0])
    checks.append(
        ("query_similar() on an empty collection returns []", empty_results == [])
    )
    checks.append(
        (
            "count() is 0 before anything is stored",
            vector_store.get_collection().count() == 0,
        )
    )

    print("Storing sample chunks...")
    chunks = [
        FakeChunk(
            "Photosynthesis converts light into chemical energy.", "bio.pdf", 1, 0
        ),
        FakeChunk("Chlorophyll absorbs sunlight in plant cells.", "bio.pdf", 1, 1),
        FakeChunk(
            "Newton's second law: force equals mass times acceleration.",
            "physics.pdf",
            1,
            0,
        ),
    ]
    # Hand-crafted vectors standing in for real embeddings: the two bio
    # chunks are close together, the physics chunk is far from both.
    embeddings = [
        [1.0, 0.8, 0.0],
        [0.6, 0.9, 0.0],
        [0.0, 0.0, 1.0],
    ]
    vector_store.store_chunks(chunks, embeddings)
    checks.append(
        (
            "count() is 3 after storing 3 chunks",
            vector_store.get_collection().count() == 3,
        )
    )

    print("Querying for similar chunks...")
    results = vector_store.query_similar([1.0, 0.85, 0.0], top_k=3)
    print("Results (nearest first):")
    for r in results:
        print(
            f"  distance={r['distance']:.4f}  source={r['source']}  page={r['page_number']}  {r['text'][:60]!r}"
        )

    checks.append(("3 results returned for top_k=3", len(results) == 3))
    checks.append(
        (
            "Closest match is a bio.pdf chunk about photosynthesis",
            bool(results)
            and results[0]["source"] == "bio.pdf"
            and "Photosynthesis" in results[0]["text"],
        )
    )
    checks.append(
        (
            "Farthest match is the unrelated physics.pdf chunk",
            bool(results) and results[-1]["source"] == "physics.pdf",
        )
    )
    distances = [r["distance"] for r in results]
    checks.append(
        (
            "Results are ordered nearest-first (ascending distance)",
            distances == sorted(distances),
        )
    )

    print("\nRe-storing the same chunks (checking upsert doesn't duplicate)...")
    vector_store.store_chunks(chunks, embeddings)
    checks.append(
        (
            "count() still 3 after re-storing identical chunks (upsert, not duplicate)",
            vector_store.get_collection().count() == 3,
        )
    )

    print("Checking mismatched-length input is rejected...")
    try:
        vector_store.store_chunks(chunks, embeddings[:2])
        checks.append(("store_chunks() raises ValueError on mismatched lengths", False))
    except ValueError:
        checks.append(("store_chunks() raises ValueError on mismatched lengths", True))

    print("\nResults:")
    all_passed = True
    for description, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {description}")

    shutil.rmtree(TEST_PERSIST_DIR, ignore_errors=True)  # clean up after ourselves

    print(
        "\n"
        + ("All checks passed." if all_passed else "Some checks FAILED — see above.")
    )
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
