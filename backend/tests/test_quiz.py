"""
test_quiz.py — verify the POST /quiz endpoint end-to-end.

Same approach as test_query.py: a standalone FastAPI app around just the
quiz router, a pre-populated test-only vector store, and the embedding
model + Groq client both stubbed out so this runs fully offline.

Usage:
    python tests/test_quiz.py
"""

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np  # noqa: E402


class FakeEmbeddingModel:
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

TEST_PERSIST_DIR = Path(__file__).parent / "fixtures" / "chroma_test_data_quiz"
import services.vector_store as vector_store  # noqa: E402

vector_store.PERSIST_DIRECTORY = str(TEST_PERSIST_DIR)

import os  # noqa: E402

os.environ["GROQ_API_KEY"] = "fake-key-for-testing"
import services.generation as generation  # noqa: E402

VALID_QUIZ_JSON = json.dumps(
    [
        {
            "question": "What does photosynthesis convert light into?",
            "options": ["Heat", "Chemical energy", "Sound", "Motion"],
            "correct_answer": "Chemical energy",
        },
        {
            "question": "Where does photosynthesis occur in a plant cell?",
            "options": ["Nucleus", "Mitochondria", "Chloroplast", "Ribosome"],
            "correct_answer": "Chloroplast",
        },
    ]
)


def make_fake_client(response_text=VALID_QUIZ_JSON):
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=response_text))]
    client.chat.completions.create.return_value = response
    return client


generation._get_client = lambda: make_fake_client()

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from routers import quiz  # noqa: E402


class FakeChunk:
    def __init__(self, text, source, page_number, chunk_index):
        self.text = text
        self.source = source
        self.page_number = page_number
        self.chunk_index = chunk_index


def main() -> None:
    checks: list[tuple[str, bool]] = []
    shutil.rmtree(TEST_PERSIST_DIR, ignore_errors=True)

    app = FastAPI()
    app.include_router(quiz.router)
    client = TestClient(app)

    # Check the empty-store case FIRST, before anything is stored -- Chroma
    # doesn't handle its on-disk data being deleted out from under an
    # already-open client mid-process, so "empty" has to mean "nothing
    # written yet," not "deleted after being populated."
    print("Requesting a quiz when the vector store is completely empty...")
    response = client.post("/quiz", json={"topic": "photosynthesis"})
    print(f"  status={response.status_code}  body={response.json()}")
    checks.append(
        (
            "Empty vector store -> 404, not a silent empty quiz",
            response.status_code == 404,
        )
    )
    # NOTE: an unrelated topic against a NON-empty store (e.g. asking for a
    # "quantum computing" quiz when only biology notes are stored) currently
    # still returns the closest available matches rather than 404 -- vector
    # search always returns its top-k nearest results, even if the nearest
    # thing available is a poor match. There's no relevance/distance
    # threshold yet to catch that case; calibrating one needs real
    # embeddings from the real model to pick a sensible cutoff, not a
    # guessed number. Worth tuning once you've seen real distance values
    # from your own content (query_cli.py prints them).

    from services.embeddings import embed_chunks

    chunks = [
        FakeChunk(
            "Photosynthesis converts light energy into chemical energy.",
            "bio.pdf",
            1,
            0,
        ),
        FakeChunk("Chlorophyll absorbs sunlight in chloroplasts.", "bio.pdf", 2, 1),
    ]
    vector_store.store_chunks(chunks, embed_chunks(chunks))

    print("\nRequesting a quiz on a topic with stored content...")
    response = client.post(
        "/quiz", json={"topic": "photosynthesis", "num_questions": 2, "top_k": 2}
    )
    print(f"  status={response.status_code}")
    body = response.json()
    print(f"  topic={body.get('topic')!r}")
    for q in body.get("questions", []):
        print(f"    Q: {q['question']}")
        print(f"       options={q['options']}  correct={q['correct_answer']!r}")

    checks.append(("Quiz request returns 200", response.status_code == 200))
    checks.append(("Topic is echoed back", body.get("topic") == "photosynthesis"))
    checks.append(("Two questions returned", len(body.get("questions", [])) == 2))
    questions = body.get("questions", [])
    checks.append(
        ("Each question has 4 options", all(len(q["options"]) == 4 for q in questions))
    )
    checks.append(
        (
            "Each correct_answer is among its own options",
            all(q["correct_answer"] in q["options"] for q in questions),
        )
    )

    print("\nRequesting a quiz with an empty topic (should be rejected)...")
    response = client.post("/quiz", json={"topic": "   "})
    checks.append(("Empty topic rejected with 400", response.status_code == 400))

    print("\nRequesting a quiz with num_questions=0 (should be rejected)...")
    response = client.post(
        "/quiz", json={"topic": "photosynthesis", "num_questions": 0}
    )
    checks.append(("num_questions=0 rejected with 400", response.status_code == 400))

    print("\nSimulating the model returning malformed JSON...")
    generation._get_client = lambda: make_fake_client(
        "Sure! Here's your quiz: 1. What is..."
    )
    response = client.post("/quiz", json={"topic": "photosynthesis"})
    print(f"  status={response.status_code}  body={response.json()}")
    checks.append(
        (
            "Malformed model output surfaces as 502, not a raw crash",
            response.status_code == 502,
        )
    )
    generation._get_client = lambda: make_fake_client()  # restore

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
