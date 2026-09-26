"""
Upload endpoint router.

Goal: accept an uploaded PDF over HTTP and run it through the full
ingestion pipeline — parse & chunk (ingestion.py), embed (embeddings.py),
store (vector_store.py) — then report back what was stored. This is the
one place those three service modules get wired together into an actual
API request; it contains no parsing/chunking/embedding logic of its own,
only orchestration, per the project's routers-vs-services convention.

Stages:
    1. Receive & validate the upload  -> check extension, save to a temp file
    2. Run the ingestion pipeline     -> ingestion -> embeddings -> vector_store
    3. Clean up & respond             -> delete the temp file, return UploadResponse
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from models.schemas import UploadResponse
from services.embeddings import embed_chunks
from services.ingestion import DocumentParsingError, process_document
from services.vector_store import store_chunks

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile) -> UploadResponse:
    # =========================================================================
    # STAGE 1: Receive & validate the upload
    # =========================================================================
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF files are supported, got '{file.filename}'",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # process_document() needs a real file path, but UploadFile only gives
    # us bytes in memory — write them to a temp file so ingestion.py can
    # work exactly as it does when called directly.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        # =====================================================================
        # STAGE 2: Run the ingestion pipeline
        # =====================================================================
        try:
            chunks = process_document(tmp_path)
        except DocumentParsingError as exc:
            # A readable-but-unusable PDF (e.g. scanned/image-only) is a
            # client-side problem with the file itself, not a server error.
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # process_document() tags each chunk's `source` with the temp
        # file's random name (e.g. "tmp8f3k2a.pdf"), since that's the only
        # path it ever sees. Swap in the real uploaded filename so stored
        # metadata — and re-upload upsert behavior in vector_store.py — is
        # keyed on something meaningful.
        for chunk in chunks:
            chunk.source = file.filename

        vectors = embed_chunks(chunks)
        store_chunks(chunks, vectors)

        # =====================================================================
        # STAGE 3: Clean up & respond
        # =====================================================================
        pages_processed = len({chunk.page_number for chunk in chunks})

        return UploadResponse(
            filename=file.filename,
            pages_processed=pages_processed,
            chunks_stored=len(chunks),
        )
    finally:
        tmp_path.unlink(missing_ok=True)
