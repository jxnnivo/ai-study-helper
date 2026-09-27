"""
Quiz endpoint router.

Goal: accept a topic over HTTP, retrieve stored chunks related to it, and
generate a set of multiple-choice quiz questions grounded in that content.
Same retrieval step as query.py — the difference is entirely in what's
asked of Groq: a quiz (structured JSON) instead of a direct answer.

Stages:
    1. Receive & validate the topic
    2. Embed it and retrieve similar chunks
    3. Generate quiz questions and respond
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import QuizQuestion, QuizRequest, QuizResponse
from services.embeddings import embed_query
from services.generation import GenerationError, generate_quiz
from services.vector_store import query_similar

router = APIRouter()


@router.post("/quiz", response_model=QuizResponse)
async def create_quiz(request: QuizRequest) -> QuizResponse:
    # =========================================================================
    # STAGE 1: Receive & validate
    # =========================================================================
    if not request.topic or not request.topic.strip():
        raise HTTPException(status_code=400, detail="topic must not be empty")
    if request.num_questions < 1:
        raise HTTPException(status_code=400, detail="num_questions must be at least 1")

    # =========================================================================
    # STAGE 2: Embed the topic and retrieve similar chunks
    # =========================================================================
    query_vector = embed_query(request.topic)
    matches = query_similar(query_vector, top_k=request.top_k)

    if not matches:
        # Unlike query.py, there's no reasonable quiz to generate with zero
        # source material -- an "answer" can honestly say "I don't know,"
        # but a quiz has nothing to ask about.
        raise HTTPException(
            status_code=404,
            detail=f"No stored notes found related to '{request.topic}'. Upload some notes first.",
        )

    # =========================================================================
    # STAGE 3: Generate quiz questions and respond
    # =========================================================================
    try:
        raw_questions = generate_quiz(
            request.topic, matches, num_questions=request.num_questions
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return QuizResponse(
        topic=request.topic,
        questions=[QuizQuestion(**q) for q in raw_questions],
    )
