"""
Pydantic request/response contracts for the API layer.

Per the project's own convention: routers/ handles HTTP concerns, services/
handles business logic, and all schema validation lives here in one place
so routers and services never need to agree on raw dicts.

NOTE: if you already have other schemas in this file (for query.py or
quiz.py stubs), add UploadResponse alongside them rather than replacing
the whole file — this version only defines what upload.py needs.
"""

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Returned by POST /upload after a document has been ingested,
    embedded, and stored."""

    filename: str
    pages_processed: int
    chunks_stored: int
