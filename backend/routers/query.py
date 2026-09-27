"""
Query endpoint router.

Goal: accept a natural-language question over HTTP, retrieve the most
relevant stored chunks, and generate an answer grounded in them — tying
embeddings.py, vector_store.py, and generation.py together into one
request. Same orchestration-only shape as upload.py: no retrieval or
generation logic lives here, only the sequencing of calls to services/.

Stages:
    1. Receive & validate the question
    2. Embed it and retrieve similar chunks
    3. Generate an answer and respond
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import QueryRequest, QueryResponse, SourceExcerpt
from services.embeddings import embed_query
from services.generation import GenerationError, generate_answer
from services.vector_store import query_similar

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest) -> QueryResponse:
    # =========================================================================
    # STAGE 1: Receive & validate
    # =========================================================================
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    # =========================================================================
    # STAGE 2: Embed the question and retrieve similar chunks
    # =========================================================================
    query_vector = embed_query(request.question)
    matches = query_similar(query_vector, top_k=request.top_k)

    # =========================================================================
    # STAGE 3: Generate an answer and respond
    # =========================================================================
    try:
        answer = generate_answer(request.question, matches)
    except GenerationError as exc:
        # The retrieval half of the request succeeded; it's specifically
        # the external Groq call that failed (missing key, network issue,
        # rate limit) -- a 502 (bad upstream response) fits better than a
        # 500, since the failure originates outside this server.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return QueryResponse(
        question=request.question,
        answer=answer,
        sources=[
            SourceExcerpt(
                source=m["source"], page_number=m["page_number"], text=m["text"]
            )
            for m in matches
        ],
    )
