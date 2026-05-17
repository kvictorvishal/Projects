"""
nodes.py — The 4 LangGraph Nodes

Node 1 : query_analysis    → rewrites / classifies the query
Node 2 : retrieval         → vector store similarity search
Node 3 : document_grading  → LLM grades each chunk as relevant / irrelevant
Node 4 : generation        → LLM generates answer with citations
"""

import json
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.state import GraphState
from app.config import get_llm, get_retriever, MAX_RETRIES


# ── Shared LLM instance ─────────────────────────────────────────────────────
_llm = None

def llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


# ═══════════════════════════════════════════════════════════════════════════
# Node 1 — Query Analysis
# ═══════════════════════════════════════════════════════════════════════════

QUERY_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at improving search queries for a technical documentation system.

Given the user's question:
1. Rewrite it to be clearer and more specific for semantic search
2. Add relevant technical synonyms or related terms if helpful
3. Classify the query type as one of: conceptual | how-to | troubleshooting | api-reference

Respond ONLY with valid JSON in this exact format (no markdown, no explanation):
{{
  "rewritten_query": "<improved query>",
  "query_type": "<conceptual|how-to|troubleshooting|api-reference>"
}}"""),
    ("human", "User question: {question}"),
])


def query_analysis_node(state: GraphState) -> GraphState:
    """Rewrite the query and classify its type."""
    print(f"\n[Node 1: Query Analysis] Original: {state['question']}")

    chain = QUERY_ANALYSIS_PROMPT | llm() | StrOutputParser()
    raw = chain.invoke({"question": state["question"]})

    try:
        result = json.loads(raw.strip())
        rewritten = result.get("rewritten_query", state["question"])
        query_type = result.get("query_type", "conceptual")
    except (json.JSONDecodeError, KeyError):
        # Graceful fallback if LLM doesn't return clean JSON
        rewritten = state["question"]
        query_type = "conceptual"

    print(f"[Node 1: Query Analysis] Rewritten: {rewritten} | Type: {query_type}")

    return {
        **state,
        "rewritten_query": rewritten,
        "query_type": query_type,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node 2 — Retrieval
# ═══════════════════════════════════════════════════════════════════════════

def retrieval_node(state: GraphState) -> GraphState:
    """Search ChromaDB and return top-k document chunks with similarity scores."""
    query = state.get("rewritten_query") or state["question"]
    print(f"\n[Node 2: Retrieval] Searching for: {query}")

    vs = get_vectorstore()
    results = vs.similarity_search_with_score(query, k=5)

    docs = []
    scores = []
    for doc, score in results:
        docs.append(doc)
        scores.append(float(score))

    print(f"[Node 2: Retrieval] Found {len(docs)} chunks, scores: {[round(s,3) for s in scores]}")

    return {
        **state,
        "retrieved_docs": docs,
        "retrieval_scores": scores,
        "relevant_docs": [],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node 3 — Document Grading (self-corrective component)
# ═══════════════════════════════════════════════════════════════════════════

GRADING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a relevance grader for a technical documentation system.

Given a user question and a retrieved document chunk, decide if the chunk is relevant.

A chunk is RELEVANT if it:
- Directly answers the question, OR
- Contains information needed to answer the question, OR
- Provides important context about the topic

A chunk is IRRELEVANT if it:
- Talks about a completely different topic
- Is too generic to help answer the specific question

Respond ONLY with valid JSON (no markdown):
{{"relevant": true}} or {{"relevant": false}}"""),
    ("human", "Question: {question}\n\nDocument chunk:\n{chunk}"),
])


def document_grading_node(state: GraphState) -> GraphState:
    """Grade each retrieved chunk as relevant or irrelevant."""
    print(f"\n[Node 3: Document Grading] Grading {len(state['retrieved_docs'])} chunks...")

    grading_chain = GRADING_PROMPT | llm() | StrOutputParser()
    relevant_docs = []

    for i, doc in enumerate(state["retrieved_docs"]):
        raw = grading_chain.invoke({
            "question": state["question"],
            "chunk": doc.page_content[:1500],   # cap to avoid token overflow
        })
        try:
            result = json.loads(raw.strip())
            is_relevant = result.get("relevant", False)
        except (json.JSONDecodeError, KeyError):
            is_relevant = False

        status = "✅ RELEVANT" if is_relevant else "❌ IRRELEVANT"
        src = doc.metadata.get("source", f"chunk_{i}")
        print(f"  [{status}] {src[:60]}")

        if is_relevant:
            relevant_docs.append(doc)

    print(f"[Node 3: Document Grading] {len(relevant_docs)}/{len(state['retrieved_docs'])} chunks passed")

    return {
        **state,
        "relevant_docs": relevant_docs,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node 4 — Generation
# ═══════════════════════════════════════════════════════════════════════════

GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a technical documentation assistant.

Answer ONLY using the provided context.

Requirements:
- Use markdown formatting
- Use bullet points where appropriate
- Include code examples if available
- Keep explanations concise and technical
- Add a short 'Sources' section at the end
- If answer is not found, say: 'I could not find this in the indexed documentation'"""),
    ("human", """Context:
{context}

Question:
{question}"""),
])


def generation_node(state: GraphState) -> GraphState:
    """Generate the final answer from relevant document chunks."""
    print(f"\n[Node 4: Generation] Generating answer from {len(state['relevant_docs'])} relevant chunks")

    # Build context string with source labels
    context_parts = []
    sources = []

    for i, doc in enumerate(state["relevant_docs"]):
        source = doc.metadata.get("source", f"Document {i+1}")
        title  = doc.metadata.get("title",  source)
        label  = f"[{i+1}] {title}"
        context_parts.append(f"{label}\n{doc.page_content}")
        if source not in sources:
            sources.append(source)

    context = "\n\n---\n\n".join(context_parts)

    chain = GENERATION_PROMPT | llm() | StrOutputParser()
    answer = chain.invoke({
        "question": state["question"],
        "context":  context,
    })

    print(f"[Node 4: Generation] Answer generated ({len(answer)} chars)")

    return {
        **state,
        "answer":  answer,
        "sources": sources,
        "generation_failed": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Fallback Node — when retries are exhausted
# ═══════════════════════════════════════════════════════════════════════════

def fallback_node(state: GraphState) -> GraphState:
    """Return a graceful 'I don't know' response after max retries."""
    print("\n[Fallback] Max retries reached — returning fallback response")
    return {
        **state,
        "answer": (
            "I'm sorry, I couldn't find relevant information in the documentation "
            "to answer your question. Please try rephrasing your question or check "
            "if the topic is covered in the available documents."
        ),
        "sources": [],
        "generation_failed": True,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Query Rewriting Node — called on retry
# ═══════════════════════════════════════════════════════════════════════════

REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at reformulating search queries.
The previous query did not return relevant results. Create a different, alternative
version of the query that might retrieve better results. Try different terminology,
broader or narrower scope, or a different angle.

Respond with ONLY the new query string, nothing else."""),
    ("human", "Original question: {question}\nFailed query: {failed_query}"),
])


def query_rewrite_node(state: GraphState) -> GraphState:
    """Rewrite the query after a failed retrieval, increment retry counter."""
    retry_count = state.get("retry_count", 0) + 1
    print(f"\n[Query Rewrite] Retry #{retry_count} — rewriting query...")

    chain = REWRITE_PROMPT | llm() | StrOutputParser()
    new_query = chain.invoke({
        "question":     state["question"],
        "failed_query": state.get("rewritten_query", state["question"]),
    })

    new_query = new_query.strip()
    print(f"[Query Rewrite] New query: {new_query}")

    return {
        **state,
        "rewritten_query": new_query,
        "retry_count":     retry_count,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Routing Function — used as conditional edge after grading
# ═══════════════════════════════════════════════════════════════════════════

def route_after_grading(state: GraphState) -> Literal["generate", "rewrite", "fallback"]:
    """
    Conditional edge logic after document_grading_node.

    - relevant docs found                  → "generate"
    - no relevant docs + retries left      → "rewrite" (query_rewrite → retrieval loop)
    - no relevant docs + retries exhausted → "fallback"
    """
    filtered_docs = state.get("relevant_docs", [])
    retries       = state.get("retry_count", 0)

    if len(filtered_docs) > 0:
        return "generate"

    if retries >= MAX_RETRIES:
        return "fallback"

    state["retry_count"] = retries + 1
    return "rewrite"
