"""Ingest a local official-source text, Markdown, or PDF file (preview by default)."""
import argparse
from pathlib import Path

from app.database.connection import SessionLocal
from app.services.document_ingestion import extract_text, ingest_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scheme-id", type=int, required=True)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--title")
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument("--apply", action="store_true", help="Write the new document and chunks; default is preview")
    args = parser.parse_args()
    content = extract_text(args.file)
    from app.services.document_ingestion import chunk_text
    chunks = chunk_text(content, chunk_size=args.chunk_size, overlap=args.overlap)
    print(f"Preview: {len(content)} extracted characters, {len(chunks)} chunks; source {args.source_name} <{args.source_url}>")
    if not args.apply:
        print("No database changes made. Re-run with --apply to ingest.")
        return
    with SessionLocal() as db:
        document, created = ingest_document(db, scheme_id=args.scheme_id, source_name=args.source_name,
            source_url=args.source_url, title=args.title, text=content,
            chunk_size=args.chunk_size, overlap=args.overlap)
        print(f"{'Ingested' if created else 'Already present'} document {document.id} ({len(document.chunks)} chunks).")


if __name__ == "__main__":
    main()
