"""
main.py
=======
FastAPI application entry point.

Pre-requisites (run before starting the server):
  python scripts/ingest_pdfs.py   # OCR + build vector index (one-time)

Start the server:
  python main.py
  OR
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()   # load .env BEFORE importing anything that reads config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import router as auth_router
from routers.chat import router as chat_router
from services.vector_service import build_or_load_vectorstore


# ── Startup env validation ─────────────────────────────────────────────────────
# Check the EXACT variable names that config.py reads from .env
REQUIRED_ENV_VARS = [
    "DOC_INTEL_ENDPOINT",
    "DOC_INTEL_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_KEY",
    "AZURE_OPENAI_API_VERSION",
    "CHAT_DEPLOYMENT",
    "EMBED_DEPLOYMENT",
]

def validate_env():
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        print("\n❌ ERROR: Missing required environment variables in your .env file:")
        for var in missing:
            print(f"   - {var}")
        print("\nCopy .env.example to .env and fill in all values.")
        print("Make sure the variable names match EXACTLY as listed above.\n")
        sys.exit(1)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_env()
    print("[startup] ✅ Environment variables loaded.")
    print("[startup] Loading vectorstore...")
    app.state.vectorstore = build_or_load_vectorstore()
    print("[startup] ✅ Vectorstore ready. Server accepting requests.")
    yield
    print("[shutdown] Server stopping.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Gujarat Info Chatbot API",
    description=(
        "RAG-powered chatbot over scanned Gujarati Government PDFs. "
        "Answers are strictly grounded in the indexed documents — no hallucination."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
