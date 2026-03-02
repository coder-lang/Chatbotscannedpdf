"""
services/vector_service.py
===========================
Handles:
  1. Parsing combined_output.txt into page-wise chunks
  2. Building / loading ChromaDB vectorstore with Azure OpenAI embeddings
  3. Multi-query search — searches with multiple query variations and combines
     results to ensure relevant chunks from ALL PDFs are retrieved
"""
import os
import re
import sys
import time
from typing import List, Optional

from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import Chroma

from core.config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_KEY,
    AZURE_OPENAI_API_VERSION,
    EMBED_DEPLOYMENT,
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION,
    OUTPUT_TXT_FILE,
    VECTOR_SEARCH_TOP_K,
)


# ── Embeddings factory ─────────────────────────────────────────────────────────
def _get_embeddings() -> AzureOpenAIEmbeddings:
    return AzureOpenAIEmbeddings(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        deployment=EMBED_DEPLOYMENT,
        openai_api_version=AZURE_OPENAI_API_VERSION,
    )


# ── Parse page chunks from combined_output.txt ────────────────────────────────
def parse_page_chunks(txt_file: str = OUTPUT_TXT_FILE) -> List[dict]:
    """
    Parse combined_output.txt into page-wise chunks with metadata.
    Each chunk = one full page block including metadata anchors.
    """
    if not os.path.exists(txt_file):
        print("\n" + "=" * 60)
        print("ERROR: combined_output.txt not found.")
        print("Run this first:  python scripts/ingest_pdfs.py")
        print("=" * 60 + "\n")
        sys.exit(1)

    with open(txt_file, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        r"(Meta Data\s*-\s*\[Document Name\s*-\s*(?P<doc>[^\,]+),\s*"
        r"Page Number\s*-\s*(?P<page>\d+)\].*?page_number_ended\s*-\s*\d+)",
        re.DOTALL | re.IGNORECASE,
    )

    chunks = []
    for m in pattern.finditer(content):
        chunks.append({
            "text":     m.group(1).strip(),
            "doc_name": m.group("doc").strip(),
            "page_no":  int(m.group("page")),
        })

    if not chunks:
        print("\nERROR: combined_output.txt has no page chunks.")
        print("Re-run: python scripts/ingest_pdfs.py\n")
        sys.exit(1)

    print(f"[vector_service] Parsed {len(chunks)} chunks from {txt_file}")
    return chunks


# ── Build or load vectorstore ──────────────────────────────────────────────────
def build_or_load_vectorstore() -> Chroma:
    """
    Fast path: load existing ChromaDB index.
    Slow path: build from scratch (runs once after ingest_pdfs.py).
    """
    embeddings = _get_embeddings()
    chroma_dir = os.path.join(CHROMA_PERSIST_DIR, CHROMA_COLLECTION)

    if os.path.exists(chroma_dir) and os.listdir(chroma_dir):
        print(f"[vector_service] Loading vectorstore from {chroma_dir}")
        return Chroma(
            persist_directory=chroma_dir,
            embedding_function=embeddings,
            collection_name=CHROMA_COLLECTION,
        )

    print("[vector_service] Building vectorstore (runs once)...")
    os.makedirs(chroma_dir, exist_ok=True)

    chunks    = parse_page_chunks()
    texts     = [c["text"]     for c in chunks]
    metadatas = [{"doc_name": c["doc_name"], "page_no": str(c["page_no"])} for c in chunks]

    BATCH    = 40
    vectordb: Optional[Chroma] = None

    for i in range(0, len(texts), BATCH):
        batch_texts = texts[i: i + BATCH]
        batch_meta  = metadatas[i: i + BATCH]
        print(f"  Embedding batch {i // BATCH + 1} / {-(-len(texts) // BATCH)}")

        for attempt in range(3):
            try:
                if vectordb is None:
                    vectordb = Chroma.from_texts(
                        texts=batch_texts,
                        metadatas=batch_meta,
                        embedding=embeddings,
                        persist_directory=chroma_dir,
                        collection_name=CHROMA_COLLECTION,
                    )
                else:
                    vectordb.add_texts(batch_texts, metadatas=batch_meta)
                break
            except Exception as e:
                if "429" in str(e) or "RateLimit" in str(e):
                    print("  Rate-limit hit, waiting 60s...")
                    time.sleep(60)
                else:
                    raise
        time.sleep(2)

    vectordb.persist()
    print(f"[vector_service] Vectorstore built → {chroma_dir}")
    return vectordb


# ── Query expander ─────────────────────────────────────────────────────────────
def _expand_query(query: str) -> List[str]:
    """
    Generate multiple search query variations from the original query.
    This ensures relevant chunks from ALL PDFs get a chance to rank.

    Strategy:
    - Original query
    - Key noun phrases extracted from query
    - Shorter keyword-only version
    """
    queries = [query]

    # Remove question words to get keyword version
    keywords = re.sub(
        r'\b(how many|how much|what is|what are|tell me|give me|'
        r'please|as of|as per|in the year|during|under|about|the|a|an)\b',
        '', query, flags=re.IGNORECASE
    ).strip()
    keywords = re.sub(r'\s+', ' ', keywords).strip()
    if keywords and keywords.lower() != query.lower():
        queries.append(keywords)

    # Extract numbers/years separately as they anchor the search
    years = re.findall(r'\b20\d{2}\b', query)
    # Remove years from query to get topic-only version
    topic_only = re.sub(r'\b20\d{2}\b', '', query).strip()
    topic_only = re.sub(r'\s+', ' ', topic_only).strip()
    if topic_only and topic_only.lower() != query.lower() and len(topic_only) > 5:
        queries.append(topic_only)

    # Deduplicate while preserving order
    seen = []
    for q in queries:
        if q.strip() and q.strip() not in seen:
            seen.append(q.strip())
    return seen


# ── Search ─────────────────────────────────────────────────────────────────────
def search_vectorstore(
    query: str,
    vectorstore: Chroma,
    k: int = VECTOR_SEARCH_TOP_K,
) -> List[dict]:
    """
    Multi-query search with deduplication.

    1. Expands query into multiple variations
    2. Searches with each variation
    3. Combines and deduplicates results
    4. Returns top-k most relevant unique chunks

    This ensures relevant chunks from ALL PDFs are retrieved
    even when the query wording doesn't exactly match stored text.
    """
    queries = _expand_query(query)
    print(f"[vector_service] Searching with {len(queries)} query variation(s): {queries}")

    seen_texts = set()
    all_results = []

    per_query_k = max(k, 15)  # fetch enough per query

    for q in queries:
        results = _single_search(q, vectorstore, k=per_query_k)
        for r in results:
            # Deduplicate by doc+page
            key = f"{r.get('doc_name')}_{r.get('page_no')}"
            if key not in seen_texts:
                seen_texts.add(key)
                all_results.append(r)

    # Return top k combined unique results
    print(f"[vector_service] Combined unique chunks: {len(all_results)}, returning top {k}")
    return all_results[:k]


def _single_search(
    query: str,
    vectorstore: Chroma,
    k: int = VECTOR_SEARCH_TOP_K,
) -> List[dict]:
    """
    Single query search — MMR first, fallback to similarity.
    """
    try:
        retriever = vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": k, "fetch_k": k * 3},
        )
        docs = retriever.invoke(query)
        if docs:
            return [{
                "text":     d.page_content,
                "doc_name": d.metadata.get("doc_name", "unknown"),
                "page_no":  d.metadata.get("page_no",  "?"),
            } for d in docs]
    except Exception:
        pass

    try:
        docs_scores = vectorstore.similarity_search_with_score(query, k=k)
        return [{
            "text":     doc.page_content,
            "doc_name": doc.metadata.get("doc_name", "unknown"),
            "page_no":  doc.metadata.get("page_no",  "?"),
            "score":    round(float(score), 4),
        } for doc, score in docs_scores]
    except Exception as e:
        print(f"[vector_service] Search failed: {e}")

    return []
