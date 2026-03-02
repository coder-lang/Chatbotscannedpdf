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
You are Gujarat Info Assistant. You answer questions using Gujarat Government
documents provided in the Context section below.

=== LANGUAGE HANDLING ===
The Context may contain English text (translated from Gujarati) or mixed content.
The user may ask in English or Gujarati — understand both and answer accordingly.
Answer in the SAME language the user asked in.

=== HOW TO USE CONTEXT ===
- ALWAYS try to find the answer from the Context before saying not found.
- The Context has multiple chunks from different pages and years — search ALL of them.
- If the topic exists anywhere in ANY chunk, extract and answer from it.
- Only respond with not-found if the topic is genuinely absent from every single chunk.

=== YEAR HANDLING ===
Follow these rules strictly based on what the user asked:

CASE 1 — User mentions a specific year (e.g. "in 2017", "as per 2018"):
  → Answer ONLY from that year's data in Context.
  → If that exact year is NOT in Context but a nearby year IS available,
    say: "Data for [requested year] is not available. Here is the data for [available year]:"
    and provide the available data. Do NOT just say not found.

CASE 2 — User does NOT mention any year:
  → Search ALL chunks across ALL years.
  → Answer from whichever year has the relevant data.
  → Always mention which year the data is from (e.g. "As per 2017 data...").
  → If data exists in multiple years, show the most recent year's data
    and mention other years if relevant.

CASE 3 — Data truly not available in any year:
  → Only then say not found.

=== OUTPUT FORMAT ===
All responses MUST be valid HTML only. No Markdown. No ``` blocks.
- <div class="answer"> ... </div>       wrap entire response
- <p> ... </p>                          paragraphs
- <h3> ... </h3>                        section headings
- <ul><li>...</li></ul>                 bullet lists
- <ol><li>...</li></ol>                 numbered lists
- <table><thead><tbody><tr><th><td>     tabular data
- <b> ... </b>                          important values
- <p class="source"> ... </p>           citations
- <p class="not-found"> ... </p>        when answer genuinely not found

=== CITATION ===
End EVERY answer with:
<p class="source">Source: Document: [name], Page: [n], Year: [year]</p>

=== STRICT RULES ===
- Do NOT guess, estimate, or use knowledge outside the Context.
- Do NOT say not found when the data exists in a different year than requested.
- ALWAYS provide whatever relevant data is available.
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
    Keep chunks matching requested years.
    Also includes adjacent year PDFs because government annual reports
    often contain data for the next year (e.g. 2017 PDF has March 2018 data).

    Search order:
    1. Exact year match in text or doc_name
    2. Adjacent year PDFs (year-1) — e.g. 2017 PDF for 2018 query
    3. If still nothing — return all chunks for LLM to explain
    """
    if not years:
        return chunks

    def chunk_matches_year(chunk, year, adjacent=False):
        text     = chunk.get("text", "")
        doc_name = str(chunk.get("doc_name", ""))
        if adjacent:
            # Check if doc is from previous year (e.g. 2017 for a 2018 query)
            prev_year = str(int(year) - 1)
            return prev_year in doc_name
        # Exact match — check text body and doc name
        return year in text or year in doc_name

    # Pass 1 — exact year match in text or doc_name
    filtered = [c for c in chunks if any(chunk_matches_year(c, y) for y in years)]
    if filtered:
        print(f"[chat_service] Year filter (exact): {len(chunks)} → {len(filtered)} chunks for {years}")
        return filtered

    # Pass 2 — include adjacent year PDFs (year-1) since annual reports span years
    adjacent = [c for c in chunks if any(chunk_matches_year(c, y, adjacent=True) for y in years)]
    if adjacent:
        print(f"[chat_service] Year filter (adjacent): found {len(adjacent)} chunks from year-1 PDFs for {years}")
        return adjacent

    # Pass 3 — nothing found, return all so LLM can explain
    print(f"[chat_service] Year {years} not found anywhere — returning all chunks for LLM")
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

    # Step 2 — Vector search across all PDFs — fetch 30 chunks for full coverage
    fetch_k = 30
    chunks  = search_vectorstore(user_message, vectorstore, k=fetch_k)

    # Step 4 — Confidence gate
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

    # Step 5 — Filter chunks by year ONLY if user specified a year
    # If no year mentioned — pass all chunks, let LLM pick latest year from context
    if query_years:
        chunks = filter_chunks_by_year(chunks, query_years)

    # Step 6 — Build context block with source labels
    context_block, citations = _build_context_block(chunks)

    # Step 7 — Augment query with year instruction
    augmented_query = user_message
    if query_years:
        augmented_query = (
            f"{user_message}\n\n"
            f"[User requested year(s): {', '.join(query_years)}. "
            f"Prioritize data from these years. If not available, provide "
            f"data from the closest available year and mention it clearly.]"
        )
    else:
        augmented_query = (
            f"{user_message}\n\n"
            f"[No year specified. Search ALL chunks across ALL years. "
            f"Answer from whichever year has this data and mention the year.]"
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

    # Deduplicate citations — keep max 1 unique source (the most relevant)
    seen = []
    for c in citations:
        if c not in seen:
            seen.append(c)
        if len(seen) == 1:
            break
    citations = seen

    return answer, citations
