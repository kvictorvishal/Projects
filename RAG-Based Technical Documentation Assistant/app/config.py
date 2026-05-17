"""
config.py — LLM + Vector Store Initialisation

Reads environment variables and returns ready-to-use LLM and
embedding instances. Import `get_llm()` and `get_vectorstore()` anywhere.
"""

import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER     = os.getenv("LLM_PROVIDER", "groq").lower()
GROQ_MODEL       = os.getenv("GROQ_MODEL",   "llama-3.1-8b-instant")
GOOGLE_MODEL     = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CHROMA_DIR       = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
TOP_K            = int(os.getenv("TOP_K_RESULTS", 5))
MAX_RETRIES      = int(os.getenv("MAX_RETRIES",   3))
COLLECTION_NAME  = "rag_docs"


# ── LLM ────────────────────────────────────────────────────────────────────

def get_llm(temperature: float = 0.0):
    """Return the configured LLM instance."""
    if LLM_PROVIDER == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=GROQ_MODEL,
            temperature=temperature,
            api_key=os.getenv("GROQ_API_KEY"),
        )
    elif LLM_PROVIDER == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=GOOGLE_MODEL,
            temperature=temperature,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    elif LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=OPENAI_MODEL,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")


# ── Embeddings ──────────────────────────────────────────────────────────────

def get_embeddings():
    """Return HuggingFace sentence-transformer embeddings (free, local)."""
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


# ── Vector Store ────────────────────────────────────────────────────────────

def get_vectorstore():
    """Return a ChromaDB vector store (persistent on disk)."""
    import chromadb
    from langchain_community.vectorstores import Chroma

    os.makedirs(CHROMA_DIR, exist_ok=True)

    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_DIR,
    )


def get_retriever(k: int = TOP_K):
    """Return a retriever from the vector store."""
    vs = get_vectorstore()
    return vs.as_retriever(search_kwargs={"k": k})
