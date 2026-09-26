"""
test_ingestion.py — verify ingestion.py's PDF chunking on a real PDF.

Unlike a typical pytest suite with synthetic fixtures, this is meant to be
run directly against a real PDF you provide, so you can see exactly what
ingestion.py does to your own document.

Usage:
    1. Put a PDF named "test_1.pdf" in this same folder (backend/tests/),
       populated with a few paragraphs of text.
    2. Run:  python test_ingestion.py
       (or point it at a different file:  python test_ingestion.py /path/to/other.pdf)

What it does:
    - Calls process_document() from services/ingestion.py on your PDF
    - Prints every chunk produced (page number, word count, text preview)
    - Runs a set of sanity checks against the result and prints PASS/FAIL
      for each, so you have more than a visual check that the split "looks right"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # so `services` is importable

from services.ingestion import CHUNK_SIZE_WORDS, DocumentParsingError, process_document

DEFAULT_PDF = Path(__file__).parent / "test_1.pdf"


def print_chunks(chunks) -> None:
    print(f"\n{len(chunks)} chunk(s) produced:")
    print("-" * 60)
    for c in chunks:
        preview = c.text[:120] + ("..." if len(c.text) > 120 else "")
        print(f"[chunk {c.chunk_index}] page {c.page_number} | {c.word_count} words")
        print(f"  {preview}\n")


def run_checks(chunks, source_name: str) -> bool:
    """A handful of sanity checks on the chunking output. Prints PASS/FAIL
    for each and returns True only if every check passed."""

    page_numbers = [c.page_number for c in chunks]

    checks = [
        ("At least one chunk was produced", len(chunks) > 0),
        (
            "Every chunk is tagged with the correct source filename",
            all(c.source == source_name for c in chunks),
        ),
        (
            f"No chunk exceeds {CHUNK_SIZE_WORDS} words",
            all(c.word_count <= CHUNK_SIZE_WORDS for c in chunks),
        ),
        (
            "Chunk indices are sequential starting at 0",
            [c.chunk_index for c in chunks] == list(range(len(chunks))),
        ),
        (
            "Page numbers never decrease as chunk index increases",
            page_numbers == sorted(page_numbers),
        ),
        ("Every chunk has non-empty text", all(c.text.strip() for c in chunks)),
        (
            "Every chunk's word_count matches its actual text",
            all(c.word_count == len(c.text.split()) for c in chunks),
        ),
    ]

    print("Sanity checks:")
    all_passed = True
    for description, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {description}")

    return all_passed


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF

    if not pdf_path.exists():
        print(f"Error: '{pdf_path}' not found.")
        print(
            f"Place a PDF named 'test_1.pdf' in {DEFAULT_PDF.parent}, or pass a path:"
        )
        print(f"  python {Path(__file__).name} /path/to/your.pdf")
        sys.exit(1)

    print(f"Running ingestion.py on: {pdf_path}")

    try:
        chunks = process_document(pdf_path)
    except (FileNotFoundError, ValueError, DocumentParsingError) as exc:
        print(f"ingestion.py raised an error: {exc}")
        sys.exit(1)

    print_chunks(chunks)
    passed = run_checks(chunks, pdf_path.name)

    print(
        "\n" + ("All checks passed." if passed else "Some checks FAILED — see above.")
    )
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
