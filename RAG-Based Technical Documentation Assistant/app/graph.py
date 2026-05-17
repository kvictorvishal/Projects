"""
graph.py — LangGraph StateGraph Definition

Wires all 4 nodes together with conditional edges.

Graph flow:
  START
    → query_analysis
    → retrieval
    → document_grading
    → [conditional edge: route_after_grading]
         "generate"  → generation → END
         "rewrite"   → query_rewrite → retrieval → document_grading  (loop)
         "fallback"  → fallback → END
"""

from langgraph.graph import StateGraph, END

MAX_RETRIES = 2

from app.state import GraphState
from app.nodes import (
    query_analysis_node,
    retrieval_node,
    document_grading_node,
    generation_node,
    fallback_node,
    query_rewrite_node,
    route_after_grading,
)
from app.hallucination_checker import hallucination_check_node


def build_graph():
    """Build and compile the RAG LangGraph workflow."""

    workflow = StateGraph(GraphState)

    # ── Register nodes ───────────────────────────────────────────────────
    workflow.add_node("query_analysis",    query_analysis_node)
    workflow.add_node("retrieval",         retrieval_node)
    workflow.add_node("document_grading",  document_grading_node)
    workflow.add_node("generation",        generation_node)
    workflow.add_node("fallback",          fallback_node)
    workflow.add_node("query_rewrite",     query_rewrite_node)
    workflow.add_node("hallucination_check", hallucination_check_node)

    # ── Entry point ──────────────────────────────────────────────────────
    workflow.set_entry_point("query_analysis")

    # ── Linear edges ─────────────────────────────────────────────────────
    workflow.add_edge("query_analysis",   "retrieval")
    workflow.add_edge("retrieval",        "document_grading")

    # ── Conditional edge after grading ───────────────────────────────────
    workflow.add_conditional_edges(
        "document_grading",
        route_after_grading,
        {
            "generate": "generation",   # → hallucination_check → END
            "rewrite":  "query_rewrite",
            "fallback": "fallback",
        },
    )

    # ── Retry loop: rewrite → retrieval → grading ─────────────────────
    workflow.add_edge("query_rewrite", "retrieval")

    # ── Terminal edges ────────────────────────────────────────────────────
    workflow.add_edge("generation",          "hallucination_check")
    workflow.add_edge("hallucination_check", END)
    workflow.add_edge("fallback",            END)

    return workflow.compile()


# Singleton compiled graph — imported by main.py
rag_graph = build_graph()
