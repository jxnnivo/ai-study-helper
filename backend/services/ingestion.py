"""
Document ingestion service — PDF only.

Goal: turn an uploaded PDF into a list of overlapping, word-count-based
text chunks that are ready to be embedded and stored in the vector store.
This file only handles "PDF on disk -> clean text chunks with metadata" —
embedding and storage happen in later stages of the pipeline.

Pipeline stages, in order:
    1. Read the PDF     -> read_pdf()
    2. Chunk the text   -> chunk_text()
    3. Package metadata -> build_chunks()
    4. Orchestrate      -> process_document()  <-- the function other code calls
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

# --- Chunking configuration -------------------------------------------------

CHUNK_SIZE_WORDS = 500
CHUNK_OVERLAP_WORDS = 75
MIN_CHUNK_SIZE_WORDS = 50


class DocumentParsingError(RuntimeError):
    """Raised when a PDF can't be read (corrupt, encrypted, no extractable text)."""


@dataclass
class Chunk:
    """One chunk of PDF text plus the metadata needed to trace it back to
    its source page for citations later."""

    text: str
    source: str
    page_number: int
    chunk_index: int
    word_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.word_count = len(self.text.split())


# =============================================================================
# STAGE 1: Read the PDF
# =============================================================================


def read_pdf(file_path: Path) -> list[tuple[int, str]]:
    """Open the PDF and extract raw text, one entry per page.

    Returns a list of (page_number, text) tuples, 1-indexed. Pages with no
    extractable text (blank pages, pure images) are skipped.
    """
    pages: list[tuple[int, str]] = []

    try:
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append((i, text))
    except Exception as exc:  # pdfplumber/pdfminer can raise several exception types
        raise DocumentParsingError(
            f"Failed to read PDF '{file_path.name}': {exc}"
        ) from exc

    if not pages:
        raise DocumentParsingError(
            f"No extractable text found in '{file_path.name}' "
            "(it may be a scanned/image-only PDF, which needs OCR — not handled yet)"
        )

    return pages


# =============================================================================
# STAGE 2: Chunk the text
# =============================================================================


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
    min_chunk_size: int = MIN_CHUNK_SIZE_WORDS,
) -> list[str]:
    """Split one page's text into overlapping, word-count-based chunks.

    - Chunks are `chunk_size` words, with `overlap` words shared between
      consecutive chunks so context isn't lost at the split point.
    - A trailing chunk smaller than `min_chunk_size` is merged into the
      previous chunk instead of being emitted on its own.
    - Text shorter than `chunk_size` is returned as a single chunk.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()
    if not words:
        return []

    if len(words) <= chunk_size:
        return [" ".join(words)]

    step = chunk_size - overlap

    # Track each chunk's start index alongside its text so a too-small
    # trailing chunk can be merged with the previous one by re-slicing from
    # the previous chunk's start through the end of the text.
    chunk_starts: list[int] = []
    chunks: list[str] = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        is_last = end == len(words)

        if is_last and (end - start) < min_chunk_size and chunk_starts:
            prev_start = chunk_starts.pop()
            chunks.pop()
            chunk_starts.append(prev_start)
            chunks.append(" ".join(words[prev_start:end]))
            break

        chunk_starts.append(start)
        chunks.append(" ".join(words[start:end]))

        if is_last:
            break
        start += step

    return chunks


# =============================================================================
# STAGE 3: Package chunks with metadata
# =============================================================================


def build_chunks(pages: list[tuple[int, str]], source_name: str) -> list[Chunk]:
    """Chunk every page's text and wrap each piece in a Chunk with metadata.

    Chunking runs per-page (not on the whole document at once) so a chunk
    never spans two pages — this keeps page-number citations accurate, at
    the cost of occasionally producing an under-sized chunk at a page's end.
    """
    chunks: list[Chunk] = []
    chunk_index = 0

    for page_number, page_text in pages:
        for piece in chunk_text(page_text):
            chunks.append(
                Chunk(
                    text=piece,
                    source=source_name,
                    page_number=page_number,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

    return chunks


# =============================================================================
# STAGE 4: Orchestrate — the entry point other code calls
# =============================================================================


def process_document(file_path: str | Path) -> list[Chunk]:
    """Read a PDF and return its ready-to-embed chunks.

    This is the function the upload endpoint calls: hand it a path to an
    uploaded PDF and get back a flat list of Chunks.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Only PDF files are supported right now, got '{path.suffix}'")

    pages = read_pdf(path)  # Stage 1
    return build_chunks(pages, path.name)  # Stages 2 + 3
