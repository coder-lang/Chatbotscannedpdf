"""
Add these routes to your main.py (or include this as a router).
This gives Streamlit access to the ACTUAL RAG chunks passed to the LLM.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from rag.vector_store import retrieve_multilingual

router = APIRouter(prefix="/debug", tags=["Debug"])


class DebugChunksRequest(BaseModel):
    query: str
    n_results: Optional[int] = 6


class ChunkDetail(BaseModel):
    chunk_number: int
    text: str                       # ← exact text passed to LLM as context
    document_name: str
    page_number: Optional[int]
    language: str
    relevance_score: float
    char_count: int
    token_estimate: int             # rough estimate: chars / 4


class DebugChunksResponse(BaseModel):
    query: str
    total_chunks_retrieved: int
    chunks: list[ChunkDetail]
    combined_context_chars: int
    combined_context_token_estimate: int
    llm_context_preview: str        # first 500 chars of what LLM actually sees


@router.post("/chunks", response_model=DebugChunksResponse)
async def get_raw_chunks(request: DebugChunksRequest):
    """
    Returns the EXACT chunks retrieved from ChromaDB that will be
    passed as context to the LLM — before any LLM call is made.

    Use this in Streamlit debug mode to see what the LLM knows.
    """
    raw_chunks = retrieve_multilingual(request.query, n_results=request.n_results)

    chunk_details = []
    for i, chunk in enumerate(raw_chunks, 1):
        meta = chunk["metadata"]
        text = chunk["text"]
        chunk_details.append(ChunkDetail(
            chunk_number=i,
            text=text,
            document_name=meta.get("document_name", "Unknown"),
            page_number=meta.get("page_number"),
            language=meta.get("language", "en"),
            relevance_score=round(chunk["relevance_score"], 4),
            char_count=len(text),
            token_estimate=len(text) // 4
        ))

    combined = "\n\n---\n\n".join(c.text for c in chunk_details)

    return DebugChunksResponse(
        query=request.query,
        total_chunks_retrieved=len(chunk_details),
        chunks=chunk_details,
        combined_context_chars=len(combined),
        combined_context_token_estimate=len(combined) // 4,
        llm_context_preview=combined[:500] + "..." if len(combined) > 500 else combined
    )
