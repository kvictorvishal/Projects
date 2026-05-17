# RAG-Based Technical Documentation Assistant

A self-corrective Retrieval-Augmented Generation (RAG) system that answers questions about technical documentation using **LangGraph**, **ChromaDB**, and **FastAPI**.

---

## Architecture Overview

```
User Question
      │
      ▼
┌─────────────────┐
│  Query Analysis  │  ← Rewrites query, classifies type (conceptual/how-to/troubleshooting/api-ref)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Retrieval     │  ← Searches ChromaDB (top-k similar chunks)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Document Grading │  ← LLM grades each chunk: relevant ✅ or irrelevant ❌
└────────┬────────┘
         │
   ┌─────┴──────────────────────┐
   │                            │
   ▼ (relevant found)           ▼ (none relevant)
┌──────────┐            ┌──────────────────┐
│Generation│            │  Retry limit?     │
│  Node    │            │  No → Query Rewrite → Retrieval (loop)
└──────────┘            │  Yes → Fallback "I don't know"
     │                  └──────────────────┘
     ▼
Final Answer + Citations
```

### LangGraph Nodes

| Node | Role |
|---|---|
| `query_analysis` | Rewrites the user query for better semantic search; classifies query type |
| `retrieval` | Searches ChromaDB for the top-k most similar document chunks |
| `document_grading` | LLM grades each chunk as relevant/irrelevant (self-corrective step) |
| `generation` | Generates a grounded answer with citations from relevant chunks |
| `query_rewrite` | Reformulates the query if no relevant docs were found (retry loop) |
| `fallback` | Returns a graceful "I don't know" after MAX_RETRIES exhausted |

### Conditional Edge (Self-Corrective Logic)

After `document_grading`, a routing function decides:
- **Relevant docs found** → `generation`
- **No relevant docs + retries left** → `query_rewrite` → `retrieval` → `document_grading` (loop)
- **No relevant docs + retries exhausted** → `fallback`

---

## Tech Stack

| Component | Technology |
|---|---|
| Workflow orchestration | LangGraph (StateGraph) |
| LLM | Groq (llama-3.1-8b-instant) / Google Gemini / OpenAI |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) — **free, local** |
| Vector store | ChromaDB (local persistent) |
| API framework | FastAPI + Uvicorn |
| Document corpus | FastAPI official documentation (4 topic pages) |

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/rag-assistant.git
cd rag-assistant
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set your LLM API key:

```env
# Choose your LLM provider: groq | google | openai
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here   # free at console.groq.com
```

> **Tip:** Groq is recommended — it's free, very fast, and needs no credit card.

### 5. Ingest documents

```bash
# Ingest the bundled docs/ directory (4 FastAPI documentation files)
python -m ingest.ingest

# OR ingest URLs directly
python -m ingest.ingest --defaults

# OR ingest a single URL
python -m ingest.ingest --url https://fastapi.tiangolo.com/tutorial/first-steps/
```

### 6. Start the API server

```bash
python run.py
```

The server starts at **http://localhost:8000**

Interactive API docs: **http://localhost:8000/docs**

---

## API Endpoints

### `POST /query` — Ask a question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I define path parameters in FastAPI?"}'
```

**Response:**
```json
{
  "question": "How do I define path parameters in FastAPI?",
  "answer": "In FastAPI, path parameters are defined by including them in curly braces within the URL path and declaring them as function arguments...\n\nSources:\n[1] fastapi_path_params",
  "sources": ["docs/fastapi_path_params.md"],
  "query_type": "how-to",
  "rewritten_query": "FastAPI path parameters definition syntax and type hints",
  "generation_failed": false,
  "session_id": "abc-123"
}
```

---

### `POST /ingest/urls` — Ingest documents from URLs

```bash
curl -X POST http://localhost:8000/ingest/urls \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://fastapi.tiangolo.com/tutorial/first-steps/"]}'
```

**Response:**
```json
{
  "message": "Successfully ingested 12 chunks",
  "urls_processed": 1,
  "chunks_added": 12
}
```

---

### `POST /ingest/files` — Upload and ingest files

```bash
curl -X POST http://localhost:8000/ingest/files \
  -F "files=@my_doc.md"
```

---

### `GET /documents` — List indexed documents

```bash
curl http://localhost:8000/documents
```

**Response:**
```json
{
  "total_chunks": 47,
  "unique_sources": 4,
  "documents": [
    {"source": "docs/fastapi_path_params.md", "chunks": 12},
    {"source": "docs/fastapi_query_params.md", "chunks": 14},
    {"source": "docs/fastapi_request_body.md", "chunks": 11},
    {"source": "docs/fastapi_response_model.md", "chunks": 10}
  ]
}
```

---

### `POST /feedback` — Submit feedback

```bash
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc-123", "rating": 1, "comment": "Very helpful!"}'
```

---

### `GET /health` — Health check

```bash
curl http://localhost:8000/health
```

---

## Document Corpus

The default corpus covers **FastAPI official documentation** across 4 topics:

| File | Topic |
|---|---|
| `docs/fastapi_path_params.md` | Path parameters, Enum values, ordering |
| `docs/fastapi_query_params.md` | Query parameters, optional/required, validation |
| `docs/fastapi_request_body.md` | Pydantic models, nested models, field validation |
| `docs/fastapi_response_model.md` | Response models, filtering, status codes, errors |

---

## Design Decisions & Tradeoffs

### Chunking Strategy

- **Chunk size: 600 tokens, overlap: 80 tokens**
- Separators prioritize Markdown headings (`##`, `###`) then paragraphs then sentences
- *Why:* Technical docs have self-contained sections under headings. Splitting at headings preserves semantic units. 600 tokens fits a code block + explanation without truncation. 80-token overlap prevents losing context that spans chunk boundaries.

### Embedding Model

- **`all-MiniLM-L6-v2`** (HuggingFace, runs locally)
- *Why:* Free, no API key needed, fast on CPU, strong performance on technical text. Avoids adding another paid API dependency.

### LLM for Grading

- Uses the same LLM as generation (configurable)
- *Tradeoff:* Using a separate cheaper model for grading would reduce cost but adds complexity. For this scale, one model is simpler and sufficient.

### Retry Logic

- Max 3 retries with progressive query rewriting
- Each retry uses the LLM to reformulate the query differently (not just repeat it)
- *Why 3:* Balance between thoroughness and latency. Beyond 3 retries, the topic likely isn't in the corpus.

### State Schema

- All state flows through a single `GraphState` TypedDict
- `retry_count` is tracked in state so the conditional edge can enforce the limit without global variables
- `generation_failed` flag lets the API response signal to the client that no relevant docs were found

### Vector Store

- **ChromaDB** with local persistence
- *Why:* Zero setup, runs in-process, persists to disk between restarts. FAISS would be faster at scale but requires manual serialization.

---

## What I Would Improve With More Time

1. **Hallucination check node** — Verify the answer is actually supported by the retrieved context (Self-RAG pattern)
2. **Web search fallback** — When ChromaDB has no relevant results, fall back to Tavily/Serper before giving up
3. **Conversation memory** — Maintain chat history per session_id for follow-up questions
4. **Streamlit UI** — Simple frontend for interactive Q&A without using curl
5. **Async ChromaDB** — The current ChromaDB client is synchronous; wrapping in `run_in_executor` would improve FastAPI concurrency
6. **Evaluation harness** — Automated tests with known question-answer pairs to measure retrieval quality

---

## Project Structure

```
rag-assistant/
├── app/
│   ├── __init__.py
│   ├── main.py        # FastAPI application + all endpoints
│   ├── graph.py       # LangGraph StateGraph definition
│   ├── nodes.py       # All 4 nodes + routing logic
│   ├── state.py       # GraphState TypedDict schema
│   └── config.py      # LLM + ChromaDB initialisation
├── ingest/
│   ├── __init__.py
│   └── ingest.py      # Document ingestion pipeline (CLI + importable)
├── docs/              # Default document corpus (FastAPI docs)
│   ├── fastapi_path_params.md
│   ├── fastapi_query_params.md
│   ├── fastapi_request_body.md
│   └── fastapi_response_model.md
├── data/              # ChromaDB persists here (auto-created)
├── run.py             # Uvicorn entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## Why LangGraph?

LangGraph was chosen over a simple chain because this system requires:

- **Stateful workflows** — every node reads and writes a shared `GraphState` TypedDict, so information (query, docs, scores, retries) flows cleanly across the entire pipeline without global variables
- **Conditional routing** — the document grading outcome dynamically decides the next step (generate vs rewrite vs fallback), which plain LangChain chains cannot express natively
- **Retry management** — `retry_count` in state lets the graph loop back through retrieval multiple times with different queries while enforcing a hard limit (MAX_RETRIES = 2)
- **Self-corrective pipelines** — the rewrite → retrieve → grade loop is the CRAG/Self-RAG pattern; LangGraph makes this a first-class graph edge rather than imperative loop logic

---

## Chunking Strategy

- **Chunk Size: 500 tokens, Overlap: 100 tokens**
- Separators follow Markdown heading hierarchy: `##` → `###` → paragraphs → sentences
- **Why:** Preserves technical context while improving retrieval precision. Code blocks and their explanations typically fit within 500 tokens. 100-token overlap ensures sentences referencing a previous code example are not severed across chunk boundaries.

## Embedding Model

- **`sentence-transformers/all-MiniLM-L6-v2`** (runs fully locally, no API key needed)
- **Why:** Fast, lightweight, strong semantic retrieval performance on technical text. Avoids adding another paid API dependency and works fully offline.

---

## Graph Visualization

To generate a visual diagram of the LangGraph workflow:

```python
from IPython.display import Image
from app.graph import rag_graph

Image(rag_graph.get_graph().draw_mermaid_png())
```

Or save it to a PNG file:

```python
png_data = rag_graph.get_graph().draw_mermaid_png()
with open("graph.png", "wb") as f:
    f.write(png_data)
```

---

## Submission Checklist

### Must Have
- LangGraph workflow (StateGraph)
- Conditional routing (generate / rewrite / fallback)
- Query rewriting node
- Retrieval node with similarity scores
- Document grading node (LLM relevance classification)
- Retry logic (MAX_RETRIES = 2)
- ChromaDB vector store
- FastAPI with all 4 endpoints (/query, /ingest, /documents, /feedback)
- Citations in generated answers

### Strong Bonus
- Hallucination checker node (app/hallucination_checker.py)
- Streamlit UI (ui.py)
- Retrieval scores returned in API response
- Graph visualization (run draw_mermaid_png() and screenshot)
