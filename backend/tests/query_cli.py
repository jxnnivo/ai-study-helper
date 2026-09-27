"""
query_cli.py — interactively test the full retrieval + generation pipeline
from the terminal, without needing the FastAPI server or the frontend
running. Reads and writes the SAME chroma_data/ store the real app uses,
so anything you've already uploaded through the actual /upload endpoint is
queryable here too.

Usage:
    # Ingest a PDF first (skip this if you've already uploaded one through
    # the real /upload endpoint)
    python tests/query_cli.py --pdf /path/to/your/notes.pdf

    # Then ask questions interactively
    python tests/query_cli.py

    # Or do both in one go
    python tests/query_cli.py --pdf /path/to/your/notes.pdf

Requires GROQ_API_KEY to be set (in a .env file in backend/, or exported
in your shell) — this calls the REAL Groq API and the REAL embedding
model, not stubs. Type 'quit' or press Ctrl+C to exit the question loop.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # so `services` is importable

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # fine if python-dotenv isn't installed; GROQ_API_KEY can still be exported manually

from services.embeddings import embed_chunks, embed_query
from services.generation import GenerationError, generate_answer
from services.ingestion import DocumentParsingError, process_document
from services.vector_store import get_collection, query_similar, store_chunks


def ingest_pdf(pdf_path: Path) -> None:
    print(f"Ingesting {pdf_path.name}...")
    try:
        chunks = process_document(pdf_path)
    except (FileNotFoundError, ValueError, DocumentParsingError) as exc:
        print(f"Failed to ingest '{pdf_path}': {exc}")
        sys.exit(1)

    vectors = embed_chunks(chunks)
    store_chunks(chunks, vectors)
    print(f"Stored {len(chunks)} chunk(s) from {pdf_path.name}.\n")


def ask(question: str, top_k: int) -> None:
    query_vector = embed_query(question)
    matches = query_similar(query_vector, top_k=top_k)

    print(f"\nRetrieved {len(matches)} chunk(s):")
    if not matches:
        print("  (none — the vector store is empty. Ingest a PDF first with --pdf)")
    for m in matches:
        preview = m["text"][:80] + ("..." if len(m["text"]) > 80 else "")
        print(
            f"  - [{m['source']} p.{m['page_number']}] distance={m['distance']:.4f}  {preview!r}"
        )

    try:
        answer = generate_answer(question, matches)
    except GenerationError as exc:
        print(f"\nGeneration failed: {exc}")
        return

    print(f"\nAnswer:\n{answer}\n")
    print("-" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--pdf", type=Path, help="Ingest this PDF before starting the question loop"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Chunks to retrieve per question (default 5)",
    )
    args = parser.parse_args()

    if args.pdf:
        ingest_pdf(args.pdf)

    count = get_collection().count()
    print(f"Vector store currently has {count} chunk(s) stored.")
    if count == 0:
        print(
            "Tip: run with --pdf /path/to/notes.pdf to ingest something to query first."
        )
    print("\nType a question and press Enter. Type 'quit' to exit.\n")

    while True:
        try:
            question = input("Ask> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit"):
            print("Exiting.")
            break

        ask(question, top_k=args.top_k)


if __name__ == "__main__":
    main()
