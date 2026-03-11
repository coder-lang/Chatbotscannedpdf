import streamlit as st
import requests
import os
import sys

# -------------------- SESSION STATE --------------------
if "info_messages" not in st.session_state:
    st.session_state.info_messages = []
if "grievance_messages" not in st.session_state:
    st.session_state.grievance_messages = []

# -------------------- CONFIG --------------------
st.set_page_config(page_title="Chat & Grievance Portal", layout="wide")

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://10.40.108.197:8508")
DEFAULT_USER_ID  = os.getenv("DEFAULT_USER_ID", "demo_user")

CHAT_URL         = f"{BACKEND_BASE_URL}/chat"
CHAT_STREAM_URL  = f"{BACKEND_BASE_URL}/chat/stream"
GRIEVANCE_URL    = f"{BACKEND_BASE_URL}/chat/grievance"
DEBUG_CHUNKS_URL = f"{BACKEND_BASE_URL}/debug/chunks"   # ← NEW: returns actual RAG chunks


# -------------------- BACKEND HELPERS --------------------

def call_backend_chat(user_message: str) -> str:
    """Non-streaming chat call. Returns full answer string."""
    try:
        r = requests.post(CHAT_URL, json={"user_id": DEFAULT_USER_ID, "message": user_message}, timeout=60)
        body = r.json()
        if isinstance(body, dict):
            return body.get("answer") or body.get("message") or str(body)
        return str(body)
    except Exception as e:
        return f"Connection error: {e}"


def stream_llm_output(user_message: str):
    """
    Streams the LLM's OUTPUT tokens from /chat/stream.
    These are the ANSWER tokens — NOT the input RAG chunks.
    """
    payload = {"user_id": DEFAULT_USER_ID, "message": user_message}
    try:
        with requests.post(CHAT_STREAM_URL, json=payload, timeout=180, stream=True) as r:
            r.raise_for_status()
            for piece in r.iter_content(chunk_size=64):   # small chunks = smoother typing effect
                if piece:
                    yield piece.decode("utf-8", errors="ignore")
    except Exception as e:
        yield f"\n\n⚠️ Streaming error: {e}"


def fetch_raw_rag_chunks(query: str, n_results: int = 6) -> dict | None:
    """
    Calls /debug/chunks to get the EXACT documents retrieved from ChromaDB
    that will be passed as context to the LLM.

    This is what you actually want to inspect.
    """
    try:
        r = requests.post(
            DEBUG_CHUNKS_URL,
            json={"query": query, "n_results": n_results},
            timeout=30
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def call_backend_grievance(user_message: str) -> dict:
    try:
        r = requests.post(GRIEVANCE_URL, json={"user_id": DEFAULT_USER_ID, "message": user_message}, timeout=20)
        return r.json()
    except Exception as e:
        return {"message": f"Connection error: {e}"}


# -------------------- UI --------------------
st.title("Uttar Pradesh AI Chatbot")

tab1, tab2 = st.tabs(["🤖 Information Bot", "📢 Raise Grievance"])

# ==================== INFORMATION BOT ====================
with tab1:
    st.subheader("Information Bot")

    # ── Debug mode toggle ──
    col1, col2 = st.columns([3, 1])
    with col2:
        debug_mode = st.checkbox("🔍 Debug: Show RAG chunks", value=False,
                                  help="Shows the exact document chunks passed to the LLM as context")
        if debug_mode:
            n_chunks = st.slider("Max chunks to retrieve", min_value=1, max_value=10, value=6)

    # ── Render previous messages ──
    for msg in st.session_state.info_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    info_input = st.chat_input("Ask something...")

    if info_input:
        # Show user message
        st.session_state.info_messages.append({"role": "user", "content": info_input})
        with st.chat_message("user"):
            st.markdown(info_input)

        # ── DEBUG MODE: Show RAG chunks BEFORE LLM answers ──
        if debug_mode:
            with st.expander("📄 RAW CHUNKS PASSED TO LLM", expanded=True):
                with st.spinner("Retrieving chunks from ChromaDB..."):
                    debug_data = fetch_raw_rag_chunks(info_input, n_results=n_chunks)

                if "error" in debug_data:
                    st.error(f"Debug endpoint error: {debug_data['error']}")
                else:
                    st.caption(
                        f"**Query:** `{debug_data['query']}` | "
                        f"**Chunks retrieved:** {debug_data['total_chunks_retrieved']} | "
                        f"**Total chars:** {debug_data['combined_context_chars']} | "
                        f"**~Tokens:** {debug_data['combined_context_token_estimate']}"
                    )

                    # Show each chunk exactly as it will be seen by the LLM
                    for chunk in debug_data.get("chunks", []):
                        lang_flag = "🇮🇳" if chunk["language"] == "hi" else "🇬🇧"
                        score_color = "green" if chunk["relevance_score"] > 0.7 else \
                                      "orange" if chunk["relevance_score"] > 0.4 else "red"

                        st.markdown(
                            f"**Chunk #{chunk['chunk_number']}** {lang_flag} &nbsp;|&nbsp; "
                            f"📄 `{chunk['document_name']}` p.{chunk['page_number']} &nbsp;|&nbsp; "
                            f"Score: :{score_color}[**{chunk['relevance_score']}**] &nbsp;|&nbsp; "
                            f"{chunk['char_count']} chars (~{chunk['token_estimate']} tokens)",
                            unsafe_allow_html=True
                        )
                        # ← THIS IS THE EXACT TEXT GOING INTO THE LLM PROMPT
                        st.code(chunk["text"], language=None)
                        st.divider()

                    st.caption("⬆️ Above is the EXACT context the LLM receives. Everything below is the LLM's answer.")

        # ── LLM ANSWER (streaming) ──
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_answer = ""
            with st.spinner("Generating answer..."):
                for token in stream_llm_output(info_input):
                    full_answer += token
                    placeholder.markdown(full_answer, unsafe_allow_html=True)

        st.session_state.info_messages.append({"role": "assistant", "content": full_answer})


# ==================== GRIEVANCE BOT ====================
with tab2:
    st.subheader("Raise a Grievance")

    for msg in st.session_state.grievance_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    grievance_input = st.chat_input("Describe your grievance...")

    if grievance_input:
        st.session_state.grievance_messages.append({"role": "user", "content": grievance_input})

        response = call_backend_grievance(grievance_input)
        status  = response.get("status")
        ticket  = response.get("grievance_id")
        message = response.get("message", "")

        if status == "success":
            reply = f"""
            <div style='padding:10px;border-left:4px solid green;'>
                <b>✅ Your grievance has been registered successfully!</b><br>
                Ticket Number: <b>{ticket}</b>
            </div>
            """
        else:
            reply = message

        st.session_state.grievance_messages.append({"role": "assistant", "content": reply})
        st.rerun()
