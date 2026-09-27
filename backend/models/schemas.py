"""
Pydantic request/response contracts for the API layer.

Per the project's own convention: routers/ handles HTTP concerns, services/
handles business logic, and all schema validation lives here in one place
so routers and services never need to agree on raw dicts.

NOTE: if you already have other schemas in this file (e.g. for a quiz.py
stub), add these alongside them rather than replacing the whole file.
"""

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Returned by POST /upload after a document has been ingested,
    embedded, and stored."""

    filename: str
    pages_processed: int
    chunks_stored: int


class QueryRequest(BaseModel):
    """Body for POST /query."""

    question: str
    top_k: int = 5


class SourceExcerpt(BaseModel):
    """One retrieved chunk cited as a source for a generated answer."""

    source: str
    page_number: int
    text: str


class QueryResponse(BaseModel):
    """Returned by POST /query: the generated answer plus the chunks it
    was grounded in, so the frontend can show citations."""

    question: str
    answer: str
    sources: list[SourceExcerpt]


class QuizRequest(BaseModel):
    """Body for POST /quiz."""

    topic: str
    num_questions: int = 5
    top_k: int = 5


class QuizQuestion(BaseModel):
    """One multiple-choice quiz question."""

    question: str
    options: list[str]
    correct_answer: str


class QuizResponse(BaseModel):
    """Returned by POST /quiz."""

    topic: str
    questions: list[QuizQuestion]
