"""
ingest.py — Document Ingestion Pipeline

Loads technical docs, splits them into chunks, generates embeddings,
and stores everything in ChromaDB.

Usage:
    python -m ingest.ingest                    # ingest all files in docs/
    python -m ingest.ingest --url <URL>        # ingest a single URL
    python -m ingest.ingest --file path/to/f   # ingest a single file
"""

import os
import sys
import argparse
import requests
from pathlib import Path
from bs4 import BeautifulSoup

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_vectorstore, COLLECTION_NAME

# ── Chunking Strategy ────────────────────────────────────────────────────────
#
#  chunk_size=600   → large enough to hold a complete code example + explanation
#  chunk_overlap=80 → preserves context across chunk boundaries
#  separators       → respects Markdown/RST headings and code blocks before
#                     falling back to paragraphs and sentences
#
SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
)


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_file(path: str) -> list[Document]:
    """Load a local .md, .txt, or .html file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    text = p.read_text(encoding="utf-8", errors="ignore")

    if p.suffix in (".html", ".htm"):
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator="\n")

    return [Document(page_content=text, metadata={"source": str(p), "title": p.stem})]


def load_url(url: str) -> list[Document]:
    """Fetch and parse a web page, returning a single Document."""
    print(f"  Fetching: {url}")
    response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Try to extract page title
    title = soup.title.string if soup.title else url

    # Remove nav, header, footer, scripts
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Prefer main content area
    main = soup.find("main") or soup.find("article") or soup.find("div", {"role": "main"})
    text = (main or soup).get_text(separator="\n")

    # Clean up excessive whitespace
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = "\n".join(lines)

    return [Document(page_content=text, metadata={"source": url, "title": title})]


# ── Core ingestion ────────────────────────────────────────────────────────────

def ingest_documents(docs: list[Document], source_label: str = ""):
    """Split docs into chunks and upsert into ChromaDB."""
    if not docs:
        print("  No documents to ingest.")
        return 0

    chunks = SPLITTER.split_documents(docs)
    print(f"  Split into {len(chunks)} chunks")

    vs = get_vectorstore()
    vs.add_documents(chunks)

    print(f"  ✅ Ingested {len(chunks)} chunks from {source_label or 'documents'}")
    return len(chunks)


def ingest_directory(directory: str = "docs") -> int:
    """Ingest all .md, .txt, and .html files from a directory."""
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"Directory '{directory}' does not exist — skipping.")
        return 0

    total = 0
    supported = {".md", ".txt", ".html", ".htm", ".rst"}

    for file_path in sorted(dir_path.rglob("*")):
        if file_path.suffix.lower() in supported:
            print(f"\nLoading: {file_path}")
            docs = load_file(str(file_path))
            total += ingest_documents(docs, source_label=file_path.name)

    return total


def ingest_urls(urls: list[str]) -> int:
    """Ingest a list of URLs."""
    total = 0
    for url in urls:
        print(f"\nFetching: {url}")
        try:
            docs = load_url(url)
            total += ingest_documents(docs, source_label=url)
        except Exception as e:
            print(f"  ❌ Failed to fetch {url}: {e}")
    return total


# ── Default corpus URLs (FastAPI + LangChain docs) ───────────────────────────

DEFAULT_URLS = [
    "https://fastapi.tiangolo.com/tutorial/first-steps/",
    "https://fastapi.tiangolo.com/tutorial/path-params/",
    "https://fastapi.tiangolo.com/tutorial/query-params/",
    "https://fastapi.tiangolo.com/tutorial/request-body/",
    "https://fastapi.tiangolo.com/tutorial/response-model/",
]


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest documents into ChromaDB")
    parser.add_argument("--url",  type=str, help="Ingest a single URL")
    parser.add_argument("--file", type=str, help="Ingest a single local file")
    parser.add_argument("--dir",  type=str, default="docs", help="Ingest all files in a directory")
    parser.add_argument("--defaults", action="store_true", help="Ingest the default FastAPI docs URLs")
    args = parser.parse_args()

    print("=" * 60)
    print("  RAG Assistant — Document Ingestion Pipeline")
    print("=" * 60)

    total = 0

    if args.url:
        total += ingest_urls([args.url])
    elif args.file:
        docs = load_file(args.file)
        total += ingest_documents(docs, source_label=args.file)
    elif args.defaults:
        print(f"\nIngesting {len(DEFAULT_URLS)} default FastAPI documentation pages...")
        total += ingest_urls(DEFAULT_URLS)
    else:
        # Default: ingest local docs/ dir, then fall back to default URLs
        local_count = ingest_directory(args.dir)
        total += local_count
        if local_count == 0:
            print(f"\nNo local files found in '{args.dir}'. Fetching default FastAPI docs...")
            total += ingest_urls(DEFAULT_URLS)

    print(f"\n{'='*60}")
    print(f"  Total chunks indexed: {total}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
