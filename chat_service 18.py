"""
services/chat_service.py
=========================
Core RAG pipeline:
  - Persistent conversation history (JSON files)
  - Year-aware retrieval
  - HTML output
  - Strict grounding from PDFs
  - Web search fallback when answer not in PDFs
"""
import re
import requests
from typing import List, Tuple

from openai import AzureOpenAI
from langchain_community.vectorstores import Chroma

from core.config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_KEY,
    AZURE_OPENAI_API_VERSION,
    CHAT_DEPLOYMENT,
    VECTOR_SEARCH_TOP_K,
    BING_SEARCH_KEY,
    BING_SEARCH_ENDPOINT,
)
from services.vector_service import search_vectorstore
from services.conversation_service import (
    get_recent_history,
    save_message,
    summarize_if_needed,
)

_openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)

# ── System prompts ─────────────────────────────────────────────────────────────

PDF_SYSTEM_PROMPT = """
You are Gujarat Info Assistant. You answer questions using ONLY the text
provided in the Context section below. Nothing else.

=== CRITICAL: NO OUTSIDE KNOWLEDGE ===
Every sentence in your answer MUST come directly from the Context text.
Do NOT add background information, general knowledge, or explanations
about schemes, policies, or programs that are not in the Context.
If a fact is not written in the Context — do NOT include it.

=== LANGUAGE HANDLING ===
- Context may be in English, Gujarati, or mixed — read ALL chunks.
- If a chunk is in Gujarati, translate it internally and extract the answer.
- Never say "not found" just because a chunk is in Gujarati script.
- Answer in the SAME language the user asked in.

=== HOW TO ANSWER ===
- Read every single chunk in Context before responding.
- Find chunks that directly answer the question.
- Extract ONLY what is written in those chunks.
- Do NOT add anything not present in the chunks.
- If the answer is present in Context, respond with the answer.
- If the topic is completely absent from every chunk, respond with exactly:
  NOT_FOUND_IN_PDF

=== YEAR HANDLING ===
CASE 1 — User mentions a specific year:
  → Use data from that year in Context.
  → If that year is not found, say:
    "Data for [year] is not available. Closest available data is from [year]:"
    Then show that data. Never just say not found.

CASE 2 — User does NOT mention a year:
  → Search ALL chunks across ALL PDFs and ALL years.
  → Answer from whichever chunk has the most relevant data.
  → Always mention which year and document the answer is from.
  → If multiple years have data, show most recent first.

CASE 3 — Topic genuinely absent from ALL chunks:
  → Respond with exactly: NOT_FOUND_IN_PDF

=== OUTPUT FORMAT (when answer found) ===
Pure HTML only. No Markdown. No ``` blocks.
- <div class="answer"> ... </div>       wrap entire response
- <p> ... </p>                          paragraphs
- <h3> ... </h3>                        headings
- <ul><li>...</li></ul>                 bullet lists
- <ol><li>...</li></ol>                 numbered lists
- <table><thead><tbody><tr><th><td>     tables
- <b> ... </b>                          important values
- <p class="source"> ... </p>           citations

=== CITATION ===
End EVERY answer with:
<p class="source">Source: Document: [name], Page: [n], Year: [year]</p>

=== FINAL CHECKLIST ===
- Is every fact in my answer present in the Context? If NO → remove it.
- Am I adding general knowledge? If YES → remove it.
- Am I adding "X is not mentioned" sentences? If YES → remove them.
""".strip()

WEB_SYSTEM_PROMPT = """
You are Gujarat Info Assistant. The question was not found in the Gujarat
Government PDF documents. You have been provided web search results below.

Answer the question using the web search results.

Rules:
- Answer ONLY from the web search results provided.
- For every fact you state, cite the source URL.
- Be concise and accurate.
- Answer in the SAME language the user asked in.
- Always mention this answer is from the web, not from the official documents.

Output format — Pure HTML only:
- <div class="answer web-answer"> ... </div>    wrap entire response
- <p> ... </p>                                  paragraphs
- <ul><li>...</li></ul>                         bullet lists
- <b> ... </b>                                  important values
- <p class="web-source"> ... </p>               web source citation

End with:
<p class="web-source">Source: <a href="[URL]">[Website Name]</a></p>
<p class="web-notice">Note: This answer is from the web as the information was not found in the available Gujarat Government documents.</p>
""".strip()


# ── Helper functions ───────────────────────────────────────────────────────────

def extract_years_from_query(query: str) -> List[str]:
    years = set()
    for match in re.findall(r"(20\d{2})[-–]((\d{2})|20\d{2})", query):
        years.add(match[0])
        suffix = match[1]
        years.add(match[0][:2] + suffix if len(suffix) == 2 else suffix)
    for y in re.findall(r"\b(20\d{2})\b", query):
        years.add(y)
    return sorted(years)


def filter_chunks_by_year(chunks: List[dict], years: List[str]) -> List[dict]:
    if not years:
        return chunks

    def matches(chunk, year, prev=False):
        text     = chunk.get("text", "")
        doc_name = str(chunk.get("doc_name", ""))
        if prev:
            prev_year = str(int(year) - 1)
            return prev_year in doc_name
        return year in text or year in doc_name

    filtered = [c for c in chunks if any(matches(c, y) for y in years)]
    if filtered:
        print(f"[chat_service] Year filter exact: {len(chunks)}→{len(filtered)} for {years}")
        return filtered

    adjacent = [c for c in chunks if any(matches(c, y, prev=True) for y in years)]
    if adjacent:
        print(f"[chat_service] Year filter adjacent: {len(adjacent)} chunks from year-1 PDFs")
        return adjacent

    print(f"[chat_service] Year {years} not found — returning all chunks")
    return chunks


def _build_context_block(chunks: List[dict]) -> Tuple[str, List[str]]:
    if not chunks:
        return "", []
    parts, citations = [], []
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


def _translate_to_gujarati(text: str) -> str:
    gujarati_chars = sum(1 for c in text if '\u0A80' <= c <= '\u0AFF')
    if gujarati_chars > 0:
        return text
    try:
        response = _openai_client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "Translate the English text to Gujarati. Return ONLY the Gujarati translation, nothing else."
                },
                {"role": "user", "content": text}
            ],
            temperature=0,
            max_tokens=300,
        )
        translated = response.choices[0].message.content.strip()
        print(f"[chat_service] Query translated: {text[:50]} → {translated[:50]}")
        return translated
    except Exception as e:
        print(f"[chat_service] Translation failed, using original: {e}")
        return text


def _web_search(query: str) -> List[dict]:
    """
    Search the web using Bing Search API.
    Returns list of { title, url, snippet }
    """
    if not BING_SEARCH_KEY:
        print("[chat_service] Bing key not set — skipping web search")
        return []

    try:
        headers = {"Ocp-Apim-Subscription-Key": BING_SEARCH_KEY}
        params  = {
            "q":      query + " Gujarat India",
            "count":  5,
            "mkt":    "en-IN",
        }
        response = requests.get(
            BING_SEARCH_ENDPOINT,
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()

        web_results = []
        for item in results.get("webPages", {}).get("value", []):
            web_results.append({
                "title":   item.get("name", ""),
                "url":     item.get("url", ""),
                "snippet": item.get("snippet", ""),
            })
        print(f"[chat_service] Web search returned {len(web_results)} results")
        return web_results

    except Exception as e:
        print(f"[chat_service] Web search failed: {e}")
        return []


def _format_web_results(results: List[dict]) -> str:
    if not results:
        return ""
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"[Web Result {i}]\n"
            f"Title: {r['title']}\n"
            f"URL: {r['url']}\n"
            f"Content: {r['snippet']}\n"
        )
    return "\n---\n".join(parts)


# ── Main chat function ─────────────────────────────────────────────────────────

def chat(
    user_id: str,
    user_message: str,
    vectorstore: Chroma,
) -> Tuple[str, List[str]]:

    # Step 0 — Handle greetings directly, no RAG needed
    GREETINGS = {"hello", "hi", "hey", "helo", "hii", "good morning", "good afternoon",
                 "good evening", "namaste", "namaskar", "kem cho", "kem chho"}
    if user_message.strip().lower().rstrip("!.,?") in GREETINGS:
        reply = "<div class='answer'><p>Hello! How can I help you with Gujarat Government information today?</p></div>"
        save_message(user_id, "user", user_message)
        save_message(user_id, "assistant", reply)
        return reply, []

    # Step 1 — Extract years
    query_years = extract_years_from_query(user_message)
    if query_years:
        print(f"[chat_service] Years in query: {query_years}")

    # Step 2 — Translate query to Gujarati for vector search
    search_query = _translate_to_gujarati(user_message)

    # Step 3 — Vector search
    fetch_k = 40
    chunks  = search_vectorstore(search_query, vectorstore, k=fetch_k)

    # Step 4 — Limit per doc (max 3 per PDF to prevent domination)
    doc_counts = {}
    balanced   = []
    for c in chunks:
        doc = c.get("doc_name", "unknown")
        if doc_counts.get(doc, 0) < 3:
            balanced.append(c)
            doc_counts[doc] = doc_counts.get(doc, 0) + 1
    chunks = balanced
    print(f"[chat_service] Balanced chunks: {len(chunks)} from {list(doc_counts.keys())}")

    # Step 5 — Year filter
    if query_years:
        chunks = filter_chunks_by_year(chunks, query_years)

    # Step 6 — Build context
    context_block, citations = _build_context_block(chunks)

    # Step 7 — Augment query
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
            f"[No year specified. Search ALL chunks across ALL years and PDFs. "
            f"Answer from whichever chunk has the most relevant data. "
            f"Always mention which year and document the answer is from.]"
        )

    # Step 8 — Load history
    history = get_recent_history(user_id)

    # Step 9 — Call LLM with PDF context
    messages = [
        {"role": "system", "content": PDF_SYSTEM_PROMPT},
        {"role": "system", "content": f"Context (use ONLY this):\n\n{context_block}"},
        *history,
        {"role": "user", "content": augmented_query},
    ]

    response = _openai_client.chat.completions.create(
        model=CHAT_DEPLOYMENT,
        messages=messages,
        temperature=0,
        top_p=0.9,
        max_tokens=1500,
    )
    answer = response.choices[0].message.content or ""

    # Step 10 — Check if PDF had no answer → fallback to web search
    if "NOT_FOUND_IN_PDF" in answer:
        print(f"[chat_service] Not found in PDF — falling back to web search")
        web_results = _web_search(user_message)

        if web_results:
            web_context = _format_web_results(web_results)
            web_messages = [
                {"role": "system", "content": WEB_SYSTEM_PROMPT},
                {"role": "system", "content": f"Web Search Results:\n\n{web_context}"},
                *history,
                {"role": "user", "content": user_message},
            ]
            web_response = _openai_client.chat.completions.create(
                model=CHAT_DEPLOYMENT,
                messages=web_messages,
                temperature=0,
                max_tokens=1500,
            )
            answer   = web_response.choices[0].message.content or ""
            citations = [r["url"] for r in web_results[:3]]
        else:
            answer = (
                "<div class='answer'>"
                "<p class='not-found'>This information was not found in the "
                "available Gujarat Government documents and web search also "
                "did not return relevant results.</p>"
                "</div>"
            )
            citations = []

    # Step 11 — Save history
    save_message(user_id, "user",      user_message)
    save_message(user_id, "assistant", answer)
    summarize_if_needed(user_id)

    # Step 12 — Deduplicate citations
    seen = []
    for c in citations:
        if c not in seen:
            seen.append(c)
        if len(seen) == 3:
            break

    return answer, seen
