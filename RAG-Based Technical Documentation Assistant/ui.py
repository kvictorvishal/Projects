"""
ui.py — Streamlit Frontend (Bonus Feature)

Run with:  streamlit run ui.py
Requires the FastAPI server to be running at http://localhost:8000
"""

import streamlit as st
import requests
import uuid

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="RAG Documentation Assistant",
    page_icon="📚",
    layout="wide",
)

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📚 RAG Assistant")
    st.caption("Powered by LangGraph + ChromaDB")
    st.divider()

    st.subheader("📥 Ingest Documents")
    url_input = st.text_area("Paste URLs (one per line)", height=100)
    if st.button("Ingest URLs", use_container_width=True):
        urls = [u.strip() for u in url_input.strip().splitlines() if u.strip()]
        if urls:
            with st.spinner("Ingesting..."):
                resp = requests.post(f"{API_BASE}/ingest/urls", json={"urls": urls})
                if resp.ok:
                    st.success(resp.json()["message"])
                else:
                    st.error(f"Error: {resp.text}")
        else:
            st.warning("Please enter at least one URL.")

    uploaded = st.file_uploader("Upload .md / .txt / .html", accept_multiple_files=True)
    if st.button("Ingest Files", use_container_width=True) and uploaded:
        with st.spinner("Uploading..."):
            files = [("files", (f.name, f.read(), "text/plain")) for f in uploaded]
            resp = requests.post(f"{API_BASE}/ingest/files", files=files)
            if resp.ok:
                st.success(resp.json()["message"])
            else:
                st.error(f"Error: {resp.text}")

    st.divider()
    st.subheader("📄 Indexed Documents")
    if st.button("Refresh", use_container_width=True):
        resp = requests.get(f"{API_BASE}/documents")
        if resp.ok:
            data = resp.json()
            st.metric("Total Chunks", data["total_chunks"])
            st.metric("Unique Sources", data["unique_sources"])
            for doc in data["documents"]:
                st.text(f"• {doc['source'].split('/')[-1]} ({doc['chunks']} chunks)")

# ── Main chat area ─────────────────────────────────────────────────────────
st.title("Ask a Question")
st.caption("Ask anything about the indexed technical documentation.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Display message history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("📎 Sources"):
                for src in msg["sources"]:
                    st.text(f"• {src}")
        if msg.get("meta"):
            cols = st.columns(3)
            cols[0].caption(f"Type: {msg['meta'].get('query_type', '—')}")
            cols[1].caption(f"Rewritten: {msg['meta'].get('rewritten_query', '—')[:60]}")
            cols[2].caption(f"Failed: {msg['meta'].get('generation_failed', False)}")

# Input
question = st.chat_input("e.g. How do I define path parameters in FastAPI?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching documentation..."):
            try:
                resp = requests.post(
                    f"{API_BASE}/query",
                    json={"question": question, "session_id": st.session_state.session_id},
                    timeout=60,
                )
                if resp.ok:
                    data = resp.json()
                    st.markdown(data["answer"])

                    if data["sources"]:
                        with st.expander("📎 Sources"):
                            for src in data["sources"]:
                                st.text(f"• {src}")

                    cols = st.columns(3)
                    cols[0].caption(f"Type: {data.get('query_type', '—')}")
                    cols[1].caption(f"Rewritten: {data.get('rewritten_query', '—')[:60]}")

                    # Feedback buttons
                    col1, col2, _ = st.columns([1, 1, 8])
                    if col1.button("👍", key=f"up_{len(st.session_state.messages)}"):
                        requests.post(f"{API_BASE}/feedback", json={
                            "session_id": st.session_state.session_id,
                            "rating": 1,
                        })
                        st.toast("Thanks for the feedback!")
                    if col2.button("👎", key=f"dn_{len(st.session_state.messages)}"):
                        requests.post(f"{API_BASE}/feedback", json={
                            "session_id": st.session_state.session_id,
                            "rating": -1,
                        })
                        st.toast("Thanks for the feedback!")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": data["answer"],
                        "sources": data["sources"],
                        "meta": data,
                    })
                else:
                    st.error(f"API error: {resp.text}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to API. Make sure `python run.py` is running.")
