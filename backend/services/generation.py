"""
Generation service.

Goal: given a question and the chunks retrieved for it (from
vector_store.py), build a grounded prompt and call the Groq API to
generate a natural-language answer. This is the only file in the pipeline
that calls an external LLM API rather than running locally -- Groq's free
tier (no credit card required) comfortably covers typical student-project
usage, and the models it serves (Llama, etc.) are open-weight, so this
isn't in tension with using open-source models.

Also handles quiz generation: given a topic and retrieved chunks, asks
Groq for multiple-choice questions as JSON, since a quiz needs structured
data (question/options/answer) rather than free-text.

Stages:
    1. Build the prompt        -> build_prompt() / build_quiz_prompt()
    2. Call the Groq API       -> generate_answer() / generate_quiz()
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from groq import Groq

DEFAULT_MODEL = "openai/gpt-oss-20b"  # Groq's recommended free-tier successor to
# llama-3.1-8b-instant, deprecated 2026-08-16

SYSTEM_PROMPT = (
    "You are a study assistant. Answer the student's question using ONLY "
    "the provided context from their notes. If the context doesn't contain "
    "enough information to answer, say so plainly instead of guessing or "
    "using outside knowledge. Keep answers clear and concise."
)

QUIZ_SYSTEM_PROMPT = (
    "You are a quiz-writing assistant for a student studying their own "
    "notes. Given context excerpts, write multiple-choice questions that "
    "test understanding of that specific content — nothing outside it. "
    "Respond with ONLY valid JSON: a list of objects, each with exactly "
    'these keys: "question" (string), "options" (a list of exactly 4 '
    'strings), and "correct_answer" (a string that exactly matches one of '
    "the options). Do not include any text before or after the JSON, and "
    "do not wrap it in markdown code fences."
)


class GenerationError(RuntimeError):
    """Raised when the Groq API call fails, or GROQ_API_KEY is missing."""


# =============================================================================
# STAGE 1: Build the prompt
# =============================================================================


def build_prompt(question: str, matches: list[dict]) -> str:
    """Assemble retrieved context + the question into a single prompt string.

    `matches` is expected to be shaped like vector_store.py's
    query_similar() output: a list of dicts with "text", "source", and
    "page_number" keys.

    Kept as a separate, pure function (no API calls) so prompt construction
    can be tested and read without needing a Groq API key or network access.
    """
    if not matches:
        context = "(No relevant notes were found for this question.)"
    else:
        excerpts = [
            f"[Excerpt {i} — {m['source']}, page {m['page_number']}]\n{m['text']}"
            for i, m in enumerate(matches, start=1)
        ]
        context = "\n\n".join(excerpts)

    return (
        f"Context from the student's notes:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the context above."
    )


# =============================================================================
# STAGE 2: Call the Groq API
# =============================================================================


@lru_cache(maxsize=1)
def _get_client() -> "Groq":
    """Create (and cache) the Groq client, reading the API key from the
    environment. Cached the same way get_model()/get_collection() are in
    the other services, so the client is only constructed once per process.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise GenerationError(
            "GROQ_API_KEY is not set. Add it to your .env file (see "
            ".env.example) or export it as an environment variable before "
            "calling generate_answer()."
        )

    from groq import Groq  # imported lazily, mirroring the other services

    return Groq(api_key=api_key)


def generate_answer(
    question: str, matches: list[dict], model: str = DEFAULT_MODEL
) -> str:
    """Generate an answer to `question`, grounded in the retrieved `matches`.

    Returns the plain-text answer. Raises GenerationError if the API key
    is missing or the API call itself fails (network error, invalid model,
    rate limit, etc.) — callers (query.py) are expected to catch this and
    turn it into an appropriate HTTP error.
    """
    if not question or not question.strip():
        raise ValueError("question must be a non-empty string")

    client = _get_client()
    prompt = build_prompt(question, matches)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        raise GenerationError(f"Groq API call failed: {exc}") from exc

    return response.choices[0].message.content


# =============================================================================
# STAGE 1 (quiz variant): Build the quiz prompt
# =============================================================================


def build_quiz_prompt(topic: str, matches: list[dict], num_questions: int) -> str:
    """Assemble retrieved context + a request for N quiz questions.

    Same pure-function shape as build_prompt() — no API calls — so it can
    be tested without a Groq API key.
    """
    if not matches:
        context = "(No relevant notes were found for this topic.)"
    else:
        excerpts = [
            f"[Excerpt {i} — {m['source']}, page {m['page_number']}]\n{m['text']}"
            for i, m in enumerate(matches, start=1)
        ]
        context = "\n\n".join(excerpts)

    return (
        f"Context from the student's notes on '{topic}':\n\n{context}\n\n"
        f"Write {num_questions} multiple-choice quiz question(s) based ONLY "
        "on the context above. Respond with only the JSON list, nothing else."
    )


def _extract_json(raw: str) -> str:
    """Strip a markdown code fence if the model wrapped its JSON in one,
    despite being told not to — LLMs do this often enough to be worth
    defending against rather than trusting the instruction to be followed.
    """
    stripped = raw.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    return fence_match.group(1) if fence_match else stripped


# =============================================================================
# STAGE 2 (quiz variant): Call the Groq API, expecting structured JSON back
# =============================================================================


def generate_quiz(
    topic: str,
    matches: list[dict],
    num_questions: int = 5,
    model: str = DEFAULT_MODEL,
) -> list[dict]:
    """Generate `num_questions` multiple-choice quiz questions grounded in
    `matches`.

    Returns a list of dicts: {"question": str, "options": list[str],
    "correct_answer": str}. Raises GenerationError if the API call fails,
    or if the model's response isn't valid, well-formed quiz JSON — an LLM
    ignoring formatting instructions is a real failure mode, not an edge
    case, so this is validated rather than trusted.
    """
    if not topic or not topic.strip():
        raise ValueError("topic must be a non-empty string")
    if num_questions < 1:
        raise ValueError("num_questions must be at least 1")

    client = _get_client()
    prompt = build_quiz_prompt(topic, matches, num_questions)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        raise GenerationError(f"Groq API call failed: {exc}") from exc

    raw_text = response.choices[0].message.content

    try:
        questions = json.loads(_extract_json(raw_text))
    except json.JSONDecodeError as exc:
        raise GenerationError(
            f"Model did not return valid JSON for the quiz: {exc}"
        ) from exc

    if not isinstance(questions, list) or not questions:
        raise GenerationError("Model returned an empty or non-list quiz response")

    for q in questions:
        if (
            not isinstance(q, dict)
            or not {"question", "options", "correct_answer"} <= q.keys()
        ):
            raise GenerationError(f"Malformed quiz question from model: {q!r}")
        if not isinstance(q["options"], list) or len(q["options"]) < 2:
            raise GenerationError(f"Quiz question has invalid options: {q!r}")
        if q["correct_answer"] not in q["options"]:
            raise GenerationError(f"correct_answer isn't among the options: {q!r}")

    return questions
