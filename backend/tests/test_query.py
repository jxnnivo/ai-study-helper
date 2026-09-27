"""
test_query.py — verify the POST /query endpoint end-to-end.

Builds a standalone FastAPI app around just the query router, pre-populates
a test-only vector store with known chunks, and sends real HTTP requests
through FastAPI's TestClient. The embedding model and Groq API are stubbed
out (same reasons as test_upload.py / test_generation.py) so this runs
fully offline without needing your Hugging Face access or a Groq API key —
but it verifies the real orchestration logic: retrieval -> generation ->
response shape.

Usage:
    python tests/test_query.py
"""

import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(
    0, str(Path(__file__).parent.parent)
)  # so `services`/`routers` are importable

# --- Stub out sentence_transformers before anything imports embeddings.py ---
import numpy as np  # noqa: E402


class FakeEmbeddingModel:
    """Deterministic fake: same text always maps to the same vector, and
    'photosynthesis'-related text ends up close together in vector space."""

    def __init__(self, name):
        pass

    def encode(self, texts, show_progress_bar=False):
        def vec(t: str):
            t_lower = t.lower()
            if "photosynthesis" in t_lower or "plant" in t_lower or "energy" in t_lower:
                return [1.0, 0.9, 0.0]
            return [0.0, 0.1, 1.0]

        if isinstance(texts, str):
            return np.array(vec(texts))
        return np.array([vec(t) for t in texts])


fake_st_module = MagicMock()
fake_st_module.SentenceTransformer = FakeEmbeddingModel
sys.modules["sentence_transformers"] = fake_st_module

# --- Point vector_store at a throwaway test directory ---
TEST_PERSIST_DIR = Path(__file__).parent / "fixtures" / "chroma_test_data_query"
import services.vector_store as vector_store  # noqa: E402

vector_store.PERSIST_DIRECTORY = str(TEST_PERSIST_DIR)

# --- Stub out the Groq client before anything imports generation.py ---
import os  # noqa: E402

os.environ["GROQ_API_KEY"] = "fake-key-for-testing"
import services.generation as generation  # noqa: E402

fake_groq_response_text = "Plants convert sunlight into energy through photosynthesis."


def fake_client():
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=fake_groq_response_text))]
    client.chat.completions.create.return_value = response
    return client


generation._get_client = fake_client

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from routers import query  # noqa: E402


class FakeChunk:
    def __init__(self, text, source, page_number, chunk_index):
        self.text = text
        self.source = source
        self.page_number = page_number
        self.chunk_index = chunk_index


def main() -> None:
    checks: list[tuple[str, bool]] = []
    shutil.rmtree(TEST_PERSIST_DIR, ignore_errors=True)

    # Pre-populate the vector store, same way upload.py would have.
    from services.embeddings import embed_chunks

    chunks = [
        FakeChunk(
            "Photosynthesis converts light energy into chemical energy.",
            "bio.pdf",
            1,
            0,
        ),
        FakeChunk(
            "Newton's second law relates force, mass, and acceleration.",
            "physics.pdf",
            1,
            0,
        ),
    ]
    vector_store.store_chunks(chunks, embed_chunks(chunks))

    app = FastAPI()
    app.include_router(query.router)
    client = TestClient(app)

    print("Asking a question related to the stored content...")
    response = client.post(
        "/query", json={"question": "How do plants get energy?", "top_k": 2}
    )
    print(f"  status={response.status_code}")
    body = response.json()
    print(f"  answer={body.get('answer')!r}")
    print(f"  sources={[s['source'] for s in body.get('sources', [])]}")

    checks.append(("Query returns 200", response.status_code == 200))
    checks.append(
        ("Question is echoed back", body.get("question") == "How do plants get energy?")
    )
    checks.append(
        (
            "Answer text comes from the (stubbed) model",
            body.get("answer") == fake_groq_response_text,
        )
    )
    checks.append(("At least one source is returned", len(body.get("sources", [])) > 0))
    checks.append(
        (
            "Most relevant source is the bio chunk, not physics",
            bool(body.get("sources")) and body["sources"][0]["source"] == "bio.pdf",
        )
    )
    checks.append(
        (
            "Source includes the actual chunk text",
            bool(body.get("sources"))
            and "Photosynthesis" in body["sources"][0]["text"],
        )
    )

    print("\nAsking with an empty question (should be rejected)...")
    response = client.post("/query", json={"question": "   "})
    checks.append(("Empty question rejected with 400", response.status_code == 400))

    print("\nSimulating a Groq API failure...")
    failing_client = MagicMock()
    failing_client.chat.completions.create.side_effect = Exception(
        "rate limit exceeded"
    )
    generation._get_client = lambda: failing_client
    response = client.post("/query", json={"question": "How do plants get energy?"})
    print(f"  status={response.status_code}  body={response.json()}")
    checks.append(
        (
            "Groq failure surfaces as 502, not a raw 500 crash",
            response.status_code == 502,
        )
    )
    # restore the working stub for anything after this
    generation._get_client = fake_client

    print("\nResults:")
    all_passed = True
    for description, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {description}")

    shutil.rmtree(TEST_PERSIST_DIR, ignore_errors=True)

    print(
        "\n"
        + ("All checks passed." if all_passed else "Some checks FAILED — see above.")
    )
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
