"""
test_upload.py — verify the POST /upload endpoint end-to-end.

Builds a standalone FastAPI app around just the upload router (so this
doesn't depend on whatever else main.py wires up), sends real PDF bytes
through it via FastAPI's TestClient, and checks not just that a 200 comes
back but that the uploaded content actually became queryable in the
vector store — the whole point of the endpoint.

Usage:
    python tests/test_upload.py

Needs: fastapi, python-multipart, httpx, reportlab (only used here to
generate a real in-memory test PDF; not a dependency of the app itself).
"""

import io
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).parent.parent)
)  # so `services`/`routers` are importable

# Point vector_store at a throwaway test directory before anything imports
# it, so this script never touches the real chroma_data/ the app uses.
TEST_PERSIST_DIR = Path(__file__).parent / "fixtures" / "chroma_test_data_upload"
import services.vector_store as vector_store  # noqa: E402

vector_store.PERSIST_DIRECTORY = str(TEST_PERSIST_DIR)

import shutil  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from routers import upload  # noqa: E402


def make_pdf_bytes(text: str) -> bytes:
    """Generate a real, minimal one-page PDF in memory with the given text."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    text_obj = c.beginText(40, 750)
    text_obj.setFont("Helvetica", 10)
    for line in text.split(". "):
        text_obj.textLine(line.strip())
    c.drawText(text_obj)
    c.showPage()
    c.save()
    return buffer.getvalue()


def main() -> None:
    checks: list[tuple[str, bool]] = []
    shutil.rmtree(TEST_PERSIST_DIR, ignore_errors=True)

    app = FastAPI()
    app.include_router(upload.router)
    client = TestClient(app)

    # --- Happy path: upload a real PDF -----------------------------------
    print("Uploading a real PDF...")
    pdf_bytes = make_pdf_bytes(
        "Photosynthesis converts light energy into chemical energy. "
        "This happens in the chloroplasts of plant cells."
    )
    response = client.post(
        "/upload",
        files={"file": ("study_notes.pdf", pdf_bytes, "application/pdf")},
    )
    print(f"  status={response.status_code}  body={response.json()}")

    checks.append(("Upload returns 200", response.status_code == 200))
    body = response.json()
    checks.append(
        (
            "Response includes the original filename",
            body.get("filename") == "study_notes.pdf",
        )
    )
    checks.append(("At least one chunk was stored", body.get("chunks_stored", 0) > 0))
    checks.append(
        ("At least one page was processed", body.get("pages_processed", 0) > 0)
    )

    # --- Prove it's actually retrievable, not just counted ----------------
    print("\nChecking the uploaded content is actually searchable...")
    from services.embeddings import embed_query

    results = vector_store.query_similar(
        embed_query("How do plants get energy?"), top_k=1
    )
    checks.append(
        (
            "Uploaded content is queryable in the vector store afterward",
            bool(results) and "Photosynthesis" in results[0]["text"],
        )
    )
    checks.append(
        (
            "Stored chunk is tagged with the real filename, not the temp path",
            bool(results) and results[0]["source"] == "study_notes.pdf",
        )
    )

    # --- Re-upload the same file: should upsert, not duplicate ------------
    print("\nRe-uploading the same file (checking upsert, not duplication)...")
    count_before = vector_store.get_collection().count()
    client.post(
        "/upload", files={"file": ("study_notes.pdf", pdf_bytes, "application/pdf")}
    )
    count_after = vector_store.get_collection().count()
    checks.append(
        (
            "Re-uploading the same filename doesn't duplicate chunks",
            count_before == count_after,
        )
    )

    # --- Rejects non-PDF files ---------------------------------------------
    print("\nUploading a non-PDF file (should be rejected)...")
    response = client.post(
        "/upload",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
    )
    print(f"  status={response.status_code}  body={response.json()}")
    checks.append(("Non-PDF upload is rejected with 400", response.status_code == 400))

    # --- Rejects empty files -------------------------------------------------
    print("\nUploading an empty file (should be rejected)...")
    response = client.post(
        "/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    checks.append(
        ("Empty file upload is rejected with 400", response.status_code == 400)
    )

    # --- Rejects an unreadable/textless PDF ----------------------------------
    print("\nUploading a PDF with no extractable text (should be rejected)...")
    blank_buffer = io.BytesIO()
    c = canvas.Canvas(blank_buffer, pagesize=letter)
    c.showPage()  # a page with nothing drawn on it -- no extractable text
    c.save()
    response = client.post(
        "/upload",
        files={"file": ("blank.pdf", blank_buffer.getvalue(), "application/pdf")},
    )
    print(f"  status={response.status_code}  body={response.json()}")
    checks.append(("Textless PDF is rejected with 422", response.status_code == 422))

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
