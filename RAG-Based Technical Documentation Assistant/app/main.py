"""
main.py — FastAPI Application

Endpoints:
  POST /query       → Run the RAG LangGraph pipeline
  POST /ingest      → Ingest new documents (files or URLs)
  GET  /documents   → List all indexed documents in ChromaDB
  POST /feedback    → Submit thumbs-up/down feedback on an answer
  GET  /health      → Health check
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── App init ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="RAG Technical Documentation Assistant",
    description="A self-corrective RAG system built with LangGraph + ChromaDB",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Feedback storage (simple JSON file) ──────────────────────────────────────
FEEDBACK_FILE = Path("./data/feedback.json")
FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_feedback() -> list:
    if FEEDBACK_FILE.exists():
        return json.loads(FEEDBACK_FILE.read_text())
    return []


def save_feedback(data: list):
    FEEDBACK_FILE.write_text(json.dumps(data, indent=2))


# ── Pydantic Models ───────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "question": "How do I define path parameters in FastAPI?",
                "session_id": "abc123",
            }
        }


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[str]
    retrieval_scores: list[float]
    query_type: str
    rewritten_query: str
    generation_failed: bool
    session_id: str


class FeedbackRequest(BaseModel):
    session_id: str
    rating: int           # 1 = thumbs up, -1 = thumbs down
    comment: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "abc123",
                "rating": 1,
                "comment": "Very helpful answer!",
            }
        }


class IngestURLRequest(BaseModel):
    urls: list[str]

    class Config:
        json_schema_extra = {
            "example": {
                "urls": [
                    "https://fastapi.tiangolo.com/tutorial/first-steps/",
                    "https://fastapi.tiangolo.com/tutorial/path-params/",
                ]
            }
        }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """
    Submit a natural language question.
    Runs the full LangGraph RAG pipeline and returns the answer with citations.
    """
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    from app.graph import rag_graph

    session_id = request.session_id or str(uuid.uuid4())

    initial_state = {
        "question":         request.question,
        "rewritten_query":  "",
        "query_type":       "",
        "retrieved_docs":   [],
        "relevant_docs":    [],
        "answer":           "",
        "sources":          [],
        "retry_count":      0,
        "generation_failed": False,
        "retrieval_scores": [],
        "feedback":         None,
    }

    try:
        final_state = rag_graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    return QueryResponse(
        question=request.question,
        answer=final_state["answer"],
        sources=final_state["sources"],
        retrieval_scores=final_state.get("retrieval_scores", []),
        query_type=final_state.get("query_type", ""),
        rewritten_query=final_state.get("rewritten_query", request.question),
        generation_failed=final_state.get("generation_failed", False),
        session_id=session_id,
    )


@app.post("/ingest/urls")
def ingest_urls(request: IngestURLRequest):
    """
    Ingest documents from a list of URLs into the vector store.
    """
    if not request.urls:
        raise HTTPException(status_code=422, detail="No URLs provided.")

    import sys
    sys.path.insert(0, ".")
    from ingest.ingest import ingest_urls as _ingest_urls

    try:
        count = _ingest_urls(request.urls)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")

    return {
        "message": f"Successfully ingested {count} chunks",
        "urls_processed": len(request.urls),
        "chunks_added": count,
    }


@app.post("/ingest/files")
async def ingest_files(files: list[UploadFile] = File(...)):
    """
    Ingest uploaded files (.md, .txt, .html) into the vector store.
    """
    import sys
    sys.path.insert(0, ".")
    from ingest.ingest import ingest_documents, SPLITTER, load_file
    from langchain_core.documents import Document

    total_chunks = 0
    processed = []

    for upload in files:
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in {".md", ".txt", ".html", ".htm", ".rst"}:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported file type: {suffix}. Use .md, .txt, or .html",
            )

        # Save temporarily
        tmp_path = Path(f"/tmp/{upload.filename}")
        tmp_path.write_bytes(await upload.read())

        try:
            docs = load_file(str(tmp_path))
            count = ingest_documents(docs, source_label=upload.filename)
            total_chunks += count
            processed.append({"file": upload.filename, "chunks": count})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing {upload.filename}: {e}")
        finally:
            tmp_path.unlink(missing_ok=True)

    return {
        "message": f"Successfully ingested {total_chunks} chunks from {len(files)} file(s)",
        "files_processed": processed,
    }


@app.get("/documents")
def list_documents():
    """
    List all documents currently indexed in the vector store.
    Returns unique sources and total chunk count.
    """
    from app.config import get_vectorstore

    try:
        vs = get_vectorstore()
        collection = vs._collection
        result = collection.get(include=["metadatas"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not access vector store: {e}")

    metadatas = result.get("metadatas", [])
    total_chunks = len(metadatas)

    # Aggregate unique sources
    sources: dict[str, int] = {}
    for meta in metadatas:
        src = meta.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1

    return {
        "total_chunks": total_chunks,
        "unique_sources": len(sources),
        "documents": [
            {"source": src, "chunks": count}
            for src, count in sorted(sources.items())
        ],
    }


@app.post("/feedback")
def submit_feedback(request: FeedbackRequest):
    """
    Submit thumbs-up (rating=1) or thumbs-down (rating=-1) feedback
    on an answer, with an optional comment.
    """
    if request.rating not in (1, -1):
        raise HTTPException(status_code=422, detail="Rating must be 1 (👍) or -1 (👎).")

    record = {
        "id":         str(uuid.uuid4()),
        "session_id": request.session_id,
        "rating":     request.rating,
        "comment":    request.comment,
        "timestamp":  datetime.utcnow().isoformat(),
    }

    feedback_list = load_feedback()
    feedback_list.append(record)
    save_feedback(feedback_list)

    return {"message": "Feedback recorded. Thank you!", "record_id": record["id"]}


@app.get("/feedback")
def get_feedback():
    """View all collected feedback (for evaluation purposes)."""
    feedback_list = load_feedback()
    thumbs_up   = sum(1 for f in feedback_list if f["rating"] ==  1)
    thumbs_down = sum(1 for f in feedback_list if f["rating"] == -1)

    return {
        "total":       len(feedback_list),
        "thumbs_up":   thumbs_up,
        "thumbs_down": thumbs_down,
        "feedback":    feedback_list,
    }
