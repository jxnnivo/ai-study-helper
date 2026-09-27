"""
Generation service.

Goal: given a question and the chunks retrieved for it (from
vector_store.py), build a grounded prompt and call the Groq API to
generate a natural-language answer. This is the only file in the pipeline
that calls an external LLM API rather than running locally -- Groq's free
tier (no credit card required) comfortably covers typical student-project
usage, and the models it serves (Llama, etc.) are open-weight, so this
isn't in tension with using open-source models.

Stages:
    1. Build the prompt   -> build_prompt()
    2. Call the Groq API  -> generate_answer()
"""

from __future__ import annotations

import os
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
