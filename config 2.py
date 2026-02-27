"""
core/config.py
==============
Central configuration — all secrets loaded from environment variables.
Never hardcode keys here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Azure Document Intelligence ──────────────────────────────────────────────
DOC_INTEL_ENDPOINT: str = os.getenv("DOC_INTEL_ENDPOINT", "")
DOC_INTEL_KEY: str      = os.getenv("DOC_INTEL_KEY", "")

# ── Azure OpenAI ─────────────────────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT: str    = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY: str         = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
CHAT_DEPLOYMENT: str          = os.getenv("CHAT_DEPLOYMENT", "gpt-4o")
EMBED_DEPLOYMENT: str         = os.getenv("EMBED_DEPLOYMENT", "text-embedding-ada-002")

# ── ChromaDB (local vector store) ────────────────────────────────────────────
CHROMA_PERSIST_DIR: str  = os.getenv("CHROMA_PERSIST_DIR", "chroma_store")
CHROMA_COLLECTION: str   = os.getenv("CHROMA_COLLECTION", "gujarat_docs")

# ── Conversation persistence (JSON file-based, swap for CosmosDB in prod) ────
CONVERSATIONS_DIR: str = os.getenv("CONVERSATIONS_DIR", "conversation_store")

# ── JWT Auth ─────────────────────────────────────────────────────────────────
JWT_SECRET_KEY: str        = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM: str         = "HS256"
JWT_EXPIRE_MINUTES: int    = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24 hrs

# ── RAG settings ─────────────────────────────────────────────────────────────
VECTOR_SEARCH_TOP_K: int       = int(os.getenv("VECTOR_SEARCH_TOP_K", "8"))
MAX_HISTORY_TURNS: int         = int(os.getenv("MAX_HISTORY_TURNS", "10"))   # last N turns sent to LLM
CHUNK_OVERLAP_CHARS: int       = 300

# ── OCR / Indexing ───────────────────────────────────────────────────────────
INPUT_PDF_FOLDER: str  = os.getenv("INPUT_PDF_FOLDER", "input_pdfs")
OUTPUT_TXT_FILE: str   = os.getenv("OUTPUT_TXT_FILE", "output_combined_txt/combined_output.txt")
ENABLE_FOOTER_FILTER: bool   = True
ENABLE_DIGIT_NORMALIZE: bool = True
