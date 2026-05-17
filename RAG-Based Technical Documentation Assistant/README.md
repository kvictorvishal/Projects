# RAG-Based Technical Documentation Assistant

A self-corrective Retrieval-Augmented Generation (RAG) system that answers questions about technical documentation. Built with **LangGraph**, **ChromaDB**, and **FastAPI** — it doesn't just retrieve and regurgitate; it grades what it finds, rewrites bad queries, and gracefully admits when it doesn't know.

---

## What This Does (and Why It's Interesting)

Most RAG systems are a straight line: embed a question → fetch chunks → generate an answer. The problem is that similarity search often returns chunks that *look* related but don't actually answer the question. This system adds a self-corrective loop to catch that.

When you ask a question, the pipeline:
1. Rewrites and classifies your query before even touching the vector store
2. Retrieves the top-k chunks from ChromaDB
3. Has an LLM *grade* each chunk — relevant or not?
4. If nothing useful came back, it reformulates the query and tries again (up to 3 times)
5. Only generates an answer once it has something worth generating from
6. Falls back gracefully with "I don't know" rather than hallucinating

This pattern is inspired by CRAG (Corrective RAG) and Self-RAG, implemented as a LangGraph StateGraph.

---

## Architecture

```
User Question
      │
      ▼
┌─────────────────┐
│  Query Analysis  │  ← Rewrites query + classifies type
└────────┬────────┘    (conceptual / how-to / troubleshooting / api-ref)
         │
         ▼
┌─────────────────┐
│    Retrieval     │  ← Searches ChromaDB, returns top-k chunks + scores
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Document Grading │  ← LLM scores each chunk: relevant ✅ or irrelevant ❌
└────────┬────────┘
         │
   ┌─────┴──────────────────────────────────┐
   │                                        │
   ▼  relevant docs found                   ▼  nothing useful
┌──────────────┐                   ┌────────────────────┐
│  Generation  │                   │  Retries left?      │
│  (+ citations)│                  │  Yes → Query Rewrite → loop back
└──────────────┘                   │  No  → Fallback ("I don't know")
                                   └────────────────────┘
```

### LangGraph Nodes

| Node | What it does |
|---|---|
| `query_analysis` | Rewrites the raw user query for better semantic search; classifies it by type |
| `retrieval` | Searches ChromaDB for the top-k most similar chunks, returns metadata + scores |
| `document_grading` | LLM grades each chunk — this is the self-corrective heart of the system |
| `generation` | Produces a grounded answer with citations from the relevant chunks |
| `query_rewrite` | Reformulates the query when nothing relevant was found — not a repeat, a genuine rewrite |
| `fallback` | Returns a clean "I don't know" after MAX_RETRIES is exhausted |

The conditional edge after `document_grading` is what makes this a graph rather than a chain. It decides the next step dynamically based on what came back.

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Workflow | LangGraph (StateGraph) | Native conditional routing, stateful loops, retry tracking |
| LLM | Groq (llama-3.1-8b-instant) | Fast, free, no credit card required |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Runs locally, no API key, solid on technical text |
| Vector store | ChromaDB (local persistent) | Zero setup, persists between restarts, great for this scale |
| API | FastAPI + Uvicorn | Fast to write, automatic docs at `/docs` |
| Corpus | FastAPI official documentation (4 topics) | Real-world technical content, publicly available |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/rag-assistant.git
cd rag-assistant
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # Linux / macOS
# venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your API key

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
LLM_PROVIDER=groq
GROQ_API_KEY= put user secret key here 
```

Groq is the recommended default — it's free at [console.groq.com](https://console.groq.com), no credit card needed, and noticeably faster than most alternatives for this use case. The code also supports OpenAI and Google Gemini if you prefer those.

### 5. Ingest documents

```bash
# Use the bundled FastAPI docs in docs/
python -m ingest.ingest

# Or pull from URLs directly
python -m ingest.ingest --defaults

# Or a single URL
python -m ingest.ingest --url https://fastapi.tiangolo.com/tutorial/first-steps/
```

### 6. Start the server

```bash
python run.py
```

Server runs at **http://localhost:8000**. Interactive API docs at **http://localhost:8000/docs**.

---

## API Reference

### `POST /query` — Ask a question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I define path parameters in FastAPI?"}'
```

```json
{
  "question": "How do I define path parameters in FastAPI?",
  "answer": "In FastAPI, path parameters are defined by including them in curly braces...\n\nSources:\n[1] fastapi_path_params",
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

### `GET /documents` — List what's indexed

```bash
curl http://localhost:8000/documents
```

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

### `POST /feedback` — Rate an answer

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

The default corpus uses **FastAPI's official documentation** across four topics:

| File | Covers |
|---|---|
| `docs/fastapi_path_params.md` | Path parameters, Enum values, ordering rules |
| `docs/fastapi_query_params.md` | Query parameters, optional/required, validation |
| `docs/fastapi_request_body.md` | Pydantic models, nested models, field validation |
| `docs/fastapi_response_model.md` | Response models, filtering fields, status codes |

---

## Design Decisions

### Why LangGraph?

A plain LangChain chain would work for the happy path — retrieve, generate, done. But this system needs to loop: if document grading fails, the graph routes back to query rewriting and retrieval. LangGraph makes that loop explicit and manageable. The `retry_count` field in `GraphState` tracks iterations without needing global variables or ugly imperative while-loops. Each node just reads and writes shared state — clean, testable, and easy to reason about.

### Chunking strategy

Chunks are **600 tokens with 80-token overlap**, split on Markdown headings first (`##`, then `###`), then paragraphs, then sentences.

The heading-first split matters here: technical documentation is deliberately structured so each section is self-contained. Splitting on headings preserves that structure. 600 tokens fits a code block plus its surrounding explanation without truncation. The 80-token overlap handles the cases where a sentence in one chunk references context from the previous one.

*(Note: the README had two conflicting specs — 600/80 and 500/100. The implementation uses 600/80.)*

### Embedding model

`all-MiniLM-L6-v2` runs locally with no API key and handles technical text well. The main alternative would be OpenAI's `text-embedding-3-small`, which scores slightly higher on benchmarks but adds a dependency and per-call cost. For this corpus size the local model is the right call.

### Grading with the same LLM

The document grader uses the same LLM as the generator rather than a separate cheaper model. The tradeoff: using a smaller model for grading would cut cost, but at this scale it's not worth the added complexity of managing two models. One model, one configuration.

### Retry limit of 3

Three retries balances thoroughness with latency. After three reformulations of the same question, the topic almost certainly isn't in the corpus, and returning "I don't know" is more honest than spinning further. Each retry uses the LLM to genuinely rewrite the query — not just repeat it with slightly different words.

### ChromaDB over FAISS

ChromaDB runs in-process, persists to disk automatically, and requires zero configuration. FAISS would be meaningfully faster at scale (millions of vectors) but requires manual serialization and more setup. For a 50-chunk corpus, ChromaDB is the right tool.

---

## What I'd Improve With More Time

**Hallucination check** — The generated answer should be verified against the retrieved context before it goes out. Self-RAG does this with a dedicated "is this answer grounded?" node; it's the most impactful missing piece right now.

**Web search fallback** — When ChromaDB comes up empty after all retries, falling back to Tavily or Serper before giving up would make the system genuinely useful for questions outside the corpus.

**Conversation memory** — Right now each query is stateless. Storing chat history per `session_id` would allow natural follow-up questions without repeating context.

**Async ChromaDB** — The ChromaDB client is synchronous, which blocks FastAPI's event loop under concurrent requests. Wrapping it in `run_in_executor` is a small change with a meaningful concurrency improvement.

**Evaluation harness** — There's no automated way to measure whether a code change improved retrieval quality. A set of known question-answer pairs with RAGAS or a similar framework would make iteration much faster.

**Streamlit UI** — curl is fine for testing but not great for demos. A minimal Streamlit frontend would make this much easier to show to someone.

---

## Project Structure

```
rag-assistant/
├── app/
│   ├── main.py        # FastAPI app and all endpoints
│   ├── graph.py       # LangGraph StateGraph definition
│   ├── nodes.py       # All nodes + routing logic
│   ├── state.py       # GraphState TypedDict schema
│   └── config.py      # LLM and ChromaDB initialisation
├── ingest/
│   └── ingest.py      # Ingestion pipeline (CLI and importable)
├── docs/              # Default corpus (FastAPI documentation)
│   ├── fastapi_path_params.md
│   ├── fastapi_query_params.md
│   ├── fastapi_request_body.md
│   └── fastapi_response_model.md
├── data/              # ChromaDB persists here (auto-created on first run)
├── run.py             # Uvicorn entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## Visualizing the Graph

If you want to see the LangGraph workflow rendered as a diagram:

```python
from IPython.display import Image
from app.graph import rag_graph

Image(rag_graph.get_graph().draw_mermaid_png())
```

Or save to a file:

```python
png_data = rag_graph.get_graph().draw_mermaid_png()
with open("graph.png", "wb") as f:
    f.write(png_data)
```
