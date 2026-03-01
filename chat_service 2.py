"""
services/chat_service.py
=========================
Core RAG pipeline with:
  - Year-aware retrieval (fixes wrong-year hallucination)
  - Redis-based persistent conversation history
  - Auto-summarization for long conversations
  - HTML output format
  - Strict grounding — no outside knowledge used
"""
import re
from typing import List, Tuple

from openai import AzureOpenAI
from langchain_community.vectorstores import Chroma

from core.config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_KEY,
    AZURE_OPENAI_API_VERSION,
    CHAT_DEPLOYMENT,
    VECTOR_SEARCH_TOP_K,
)
from services.vector_service import search_vectorstore
from services.conversation_service import (
    get_recent_history,
    save_message,
    summarize_if_needed,
)


# ── Azure OpenAI client ────────────────────────────────────────────────────────
_openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)


# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are Gujarat Info Assistant. You answer questions using the Gujarat Government
documents provided in the Context section below.

IMPORTANT: The Context contains text extracted from scanned Gujarati government
documents. The text may be in Gujarati script, English, or a mix of both.
You MUST read and understand Gujarati text in the Context and use it to answer
questions asked in English or Gujarati. Do not say "not found" just because the
text is in Gujarati — translate it internally and extract the answer.

RULES:

1. Use ONLY information from the Context section.
   Only say "not found" if the topic is genuinely absent from ALL chunks.
   <p class="not-found">I could not find the answer to your question in the available documents.</p>

2. YEAR PRECISION (critical):
   - If user asks about a specific year, ONLY use data from that exact year.
   - If that year is not in the Context, say:
     <p class="not-found">The available documents do not contain data for that year.</p>
   - NEVER mix data from different years.

3. OUTPUT FORMAT — All responses MUST be valid HTML only:
   - <div class="answer"> ... </div>         wrap entire response
   - <p> ... </p>                            paragraphs
   - <h3> ... </h3>                          section headings
   - <ul><li>...</li></ul>                  bullet lists
   - <ol><li>...</li></ol>                  numbered lists
   - <table><thead><tbody><tr><th><td>       tabular data
   - <b> ... </b>                            important values
   - <p class="source"> ... </p>             citations
   - <p class="not-found"> ... </p>          when answer not found
   Do NOT use Markdown. Do NOT use ``` blocks. Pure HTML only.

4. CITATION — End every answer with:
   <p class="source">Source: Document: <n>, Page: <n>, Year: <year></p>

5. Use HTML tables for tabular data.

6. Do NOT guess or extrapolate values not present in the Context.

7. Answer in the same language the user used (English or Gujarati).
""".strip()


# ── Year extraction ────────────────────────────────────────────────────────────
def extract_years_from_query(query: str) -> List[str]:
    """
    Extract years from query including Indian financial year format.
    "2013-14" → ["2013", "2014"]
    "2014 data" → ["2014"]
    """
    years = set()
    for match in re.findall(r"(20\d{2})[-–]((\d{2})|20\d{2})", query):
        years.add(match[0])
        suffix = match[1]
        years.add(match[0][:2] + suffix if len(suffix) == 2 else suffix)
    for y in re.findall(r"\b(20\d{2})\b", query):
        years.add(y)
    return sorted(years)


# ── Year filter ────────────────────────────────────────────────────────────────
def filter_chunks_by_year(chunks: List[dict], years: List[str]) -> List[dict]:
    """
    Keep only chunks containing the requested years.
    If no chunks match, return all chunks so LLM can explain what years exist.
    """
    if not years:
        return chunks
    filtered = [c for c in chunks if any(y in c.get("text", "") for y in years)]
    if filtered:
        print(f"[chat_service] Year filter: {len(chunks)} → {len(filtered)} chunks for years {years}")
        return filtered
    print(f"[chat_service] Year {years} not found in chunks — returning all for LLM to explain")
    return chunks


# ── Context block builder ──────────────────────────────────────────────────────
def _build_context_block(chunks: List[dict]) -> Tuple[str, List[str]]:
    """
    Format chunks into a labelled context string.
    Each chunk labelled with source doc, page, and years present.
    """
    if not chunks:
        return "", []

    parts     = []
    citations = []

    for i, chunk in enumerate(chunks, 1):
        doc         = chunk.get("doc_name", "unknown")
        page        = chunk.get("page_no",  "?")
        text        = chunk.get("text",     "")
        chunk_years = sorted(set(re.findall(r"\b20\d{2}\b", text)))
        year_label  = f", Years: {', '.join(chunk_years)}" if chunk_years else ""
        citation    = f"Document: {doc}, Page: {page}"
        citations.append(citation)
        parts.append(f"[Chunk {i} | {citation}{year_label}]\n{text}\n")

    return "\n---\n".join(parts), citations


# ── Main chat function ─────────────────────────────────────────────────────────
def chat(
    user_id: str,
    user_message: str,
    vectorstore: Chroma,
) -> Tuple[str, List[str]]:
    """
    Full RAG pipeline for one turn.

    user_id is the Redis key for conversation history.
    Same user_id → history loads and continues.
    New user_id  → fresh conversation starts.
    """

    # Step 1 — Extract years from query
    query_years = extract_years_from_query(user_message)
    if query_years:
        print(f"[chat_service] Years in query: {query_years}")

    # Step 2 — Vector search (fetch more when years detected, will filter next)
    fetch_k = max(VECTOR_SEARCH_TOP_K, 15) if query_years else VECTOR_SEARCH_TOP_K
    chunks  = search_vectorstore(user_message, vectorstore, k=fetch_k)

    # Step 3 — Confidence gate
    if not chunks:
        reply = (
            "<div class='answer'>"
            "<p class='not-found'>I could not find relevant information "
            "in the available documents to answer your question.</p>"
            "</div>"
        )
        save_message(user_id, "user",      user_message)
        save_message(user_id, "assistant", reply)
        return reply, []

    # Step 4 — Filter chunks by year
    chunks = filter_chunks_by_year(chunks, query_years)

    # Step 5 — Build context block with source labels
    context_block, citations = _build_context_block(chunks)

    # Step 6 — Augment query with year reminder
    augmented_query = user_message
    if query_years:
        augmented_query = (
            f"{user_message}\n\n"
            f"[IMPORTANT: Answer ONLY for year(s): {', '.join(query_years)}. "
            f"If those years are not in the Context, say so clearly.]"
        )

    # Step 7 — Load persistent history from Redis
    history = get_recent_history(user_id)

    # Step 8 — Assemble messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Context (use ONLY this):\n\n{context_block}"},
        *history,
        {"role": "user", "content": augmented_query},
    ]

    # Step 9 — Call Azure OpenAI
    response = _openai_client.chat.completions.create(
        model=CHAT_DEPLOYMENT,
        messages=messages,
        temperature=0,
        top_p=0.9,
        max_tokens=1500,
    )
    answer = response.choices[0].message.content or ""

    # Step 10 — Save both turns to Redis
    save_message(user_id, "user",      user_message)
    save_message(user_id, "assistant", answer)

    # Step 11 — Summarize old messages if conversation is long
    summarize_if_needed(user_id)

    return answer, citations
