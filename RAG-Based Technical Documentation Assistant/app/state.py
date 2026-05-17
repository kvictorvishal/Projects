"""
state.py — LangGraph State Schema

Defines the TypedDict that flows between all nodes in the graph.
Every field here is shared across the entire workflow run.
"""

from typing import List, Optional, TypedDict
from langchain_core.documents import Document


class GraphState(TypedDict):
    """
    State schema for the RAG LangGraph workflow.

    Fields
    ------
    question : str
        The original user question (never mutated).
    rewritten_query : str
        The query after expansion/rewriting by the Query Analysis node.
    query_type : str
        Classification: "conceptual" | "how-to" | "troubleshooting" | "api-reference"
    retrieved_docs : List[Document]
        Raw chunks returned by the vector store (before grading).
    relevant_docs : List[Document]
        Chunks that passed the Document Grading node.
    answer : str
        Final generated answer from the Generation node.
    sources : List[str]
        Source metadata strings included in the answer.
    retry_count : int
        Tracks how many times we have rewritten + re-retrieved (max = MAX_RETRIES).
    generation_failed : bool
        True when we exceeded retries and couldn't find relevant docs.
    feedback : Optional[dict]
        Stores user feedback submitted via POST /feedback.
    """

    question: str
    rewritten_query: str
    query_type: str
    retrieved_docs: List[Document]
    relevant_docs: List[Document]
    answer: str
    sources: List[str]
    retry_count: int
    generation_failed: bool
    retrieval_scores: List[float]
    feedback: Optional[dict]
