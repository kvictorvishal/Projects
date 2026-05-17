"""
hallucination_checker.py — Bonus: Hallucination Guard Node

Verifies that the generated answer is fully grounded in the retrieved context.
Inspired by Self-RAG. Adds a post-generation verification step.
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.config import get_llm
from app.state import GraphState


HALLUCINATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a fact-checking assistant for a RAG system.

Your job is to verify whether the generated answer is fully supported by the provided context.

Rules:
- Return SUPPORTED if every claim in the answer can be traced back to the context
- Return UNSUPPORTED if the answer contains claims not present in the context
- Be strict: even one unsupported fact = UNSUPPORTED

Respond with ONLY one word: SUPPORTED or UNSUPPORTED"""),
    ("human", """Context:
{context}

Question:
{question}

Answer:
{answer}"""),
])


def verify_answer(llm, question: str, answer: str, context: str) -> str:
    """
    Check if the answer is grounded in the context.
    Returns 'SUPPORTED' or 'UNSUPPORTED'.
    """
    chain = HALLUCINATION_PROMPT | llm | StrOutputParser()
    result = chain.invoke({
        "context":  context,
        "question": question,
        "answer":   answer,
    })
    return result.content.strip() if hasattr(result, "content") else result.strip()


def hallucination_check_node(state: GraphState) -> GraphState:
    """
    Post-generation node that verifies the answer is grounded in context.
    If hallucination is detected, appends a warning to the answer.
    """
    print("\n[Hallucination Check] Verifying answer is grounded in context...")

    # Build context string from relevant docs
    context = "\n\n".join(
        doc.page_content for doc in state.get("relevant_docs", [])
    )

    llm = get_llm(temperature=0.0)
    verdict = verify_answer(
        llm=llm,
        question=state["question"],
        answer=state["answer"],
        context=context,
    )

    print(f"[Hallucination Check] Verdict: {verdict}")

    if "UNSUPPORTED" in verdict.upper():
        warning = (
            "\n\n---\n⚠️ **Warning:** This answer may contain information not fully "
            "supported by the indexed documentation. Please verify with the original sources."
        )
        return {
            **state,
            "answer": state["answer"] + warning,
        }

    return state
