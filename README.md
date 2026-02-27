# Gujarat Info Chatbot — Setup & Run Guide

A RAG-powered (Retrieval-Augmented Generation) chatbot built with FastAPI that answers
questions from scanned Gujarati Government PDF documents. Answers are strictly grounded
in the indexed documents — no hallucination.

---

## Table of Contents

1. [How It Works (Quick Overview)](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Step 1 — Clone & Install Dependencies](#step-1--clone--install-dependencies)
5. [Step 2 — Configure Environment Variables](#step-2--configure-environment-variables)
6. [Step 3 — Add Your PDFs](#step-3--add-your-pdfs)
7. [Step 4 — Run the Ingestion Pipeline (One-Time)](#step-4--run-the-ingestion-pipeline-one-time)
8. [Step 5 — Start the FastAPI Server](#step-5--start-the-fastapi-server)
9. [Step 6 — Test the API](#step-6--test-the-api)
10. [API Reference](#api-reference)
11. [Folder Structure After Setup](#folder-structure-after-setup)
12. [Troubleshooting](#troubleshooting)
13. [Production Deployment Notes](#production-deployment-notes)

---

## How It Works

```
Your 15 Scanned PDFs
        │
        ▼  [Run ONCE — Step 4]
Azure Document Intelligence (OCR)
        │   Extracts text + tables page by page
        ▼
combined_output.txt  (all pages with metadata anchors)
        │
        ▼
Azure OpenAI Embeddings → ChromaDB Vector Index
        │
        └─────────────────────────────────────────┐
                                                   │
User sends message → JWT verified → History loaded │
        │                                          │
        ▼                                          ▼
Azure OpenAI Embeddings    ChromaDB Vector Search (top 8 chunks)
        │                          │
        └──────────┬───────────────┘
                   ▼
        Azure OpenAI GPT-4o
        (temperature=0, answers ONLY from retrieved chunks)
                   │
                   ▼
        Answer + Citations saved to conversation_store/<user_id>.json
                   │
                   ▼
        Response returned to user
```

---

## Prerequisites

Make sure the following are installed and available before you begin.

| Requirement | Version | Check Command |
|---|---|---|
| Python | 3.10 or higher | `python --version` |
| pip | latest | `pip --version` |
| Git | any | `git --version` |

You also need the following **Azure credentials** ready:

| Azure Service | What You Need |
|---|---|
| Azure Document Intelligence | Endpoint URL + API Key |
| Azure OpenAI | Endpoint URL + API Key + Deployment names for GPT-4o and text-embedding-ada-002 |

> ⚠️ Make sure your Azure OpenAI resource has **two deployments created**:
> one for `gpt-4o` (or `gpt-4o-mini`) and one for `text-embedding-ada-002`.

---

## Project Structure

```
chatbot/
│
├── main.py                          # FastAPI app — entry point
│
├── core/
│   ├── config.py                    # All settings loaded from .env
│   ├── security.py                  # JWT creation, password hashing
│   └── dependencies.py              # FastAPI auth dependency (get_current_user)
│
├── models/
│   ├── user.py                      # Pydantic schemas: RegisterRequest, LoginRequest
│   └── chat.py                      # Pydantic schemas: ChatRequest, ChatResponse
│
├── routers/
│   ├── auth.py                      # POST /auth/register, POST /auth/login
│   └── chat.py                      # POST /chat, GET /chat/history, DELETE /chat/history
│
├── services/
│   ├── ocr_service.py               # Azure DI dual-pass OCR (read + layout)
│   ├── vector_service.py            # ChromaDB build/load + vector search
│   ├── chat_service.py              # Core RAG pipeline (anti-hallucination)
│   ├── conversation_service.py      # Persistent per-user chat history (JSON files)
│   └── user_store.py                # Simple user registry (JSON file)
│
├── scripts/
│   └── ingest_pdfs.py               # One-time setup: OCR → embed → index
│
├── input_pdfs/                      # ← PUT YOUR 15 PDFs HERE
├── output_combined_txt/             # Auto-created: combined_output.txt goes here
├── chroma_store/                    # Auto-created: vector index stored here
├── conversation_store/              # Auto-created: one JSON file per user
├── user_store/                      # Auto-created: user accounts stored here
│
├── .env                             # Your secrets — never commit this file
├── .env.example                     # Template for .env
└── requirements.txt                 # All Python dependencies
```

---

## Step 1 — Clone & Install Dependencies

**1.1 — Clone the repository (or copy project folder)**

```bash
git clone <your-repo-url>
cd chatbot
```

**1.2 — Create a Python virtual environment**

It is strongly recommended to use a virtual environment to avoid conflicts with
other Python projects on your machine.

```bash
# Create virtual environment
python -m venv venv

# Activate it — Windows
venv\Scripts\activate

# Activate it — macOS / Linux
source venv/bin/activate
```

You should now see `(venv)` at the beginning of your terminal prompt.

**1.3 — Install all dependencies**

```bash
pip install -r requirements.txt
```

This installs FastAPI, Azure SDKs, LangChain, ChromaDB, and all other required packages.
Installation takes 1–3 minutes depending on your internet speed.

**1.4 — Verify installation**

```bash
python -c "import fastapi, openai, chromadb, azure.ai.documentintelligence; print('All packages OK')"
```

Expected output: `All packages OK`

---

## Step 2 — Configure Environment Variables

**2.1 — Copy the example file**

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

**2.2 — Open `.env` and fill in your credentials**

```env
# ── Azure Document Intelligence ───────────────────────────────────────────────
DOC_INTEL_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
DOC_INTEL_KEY=your_document_intelligence_key_here

# ── Azure OpenAI ──────────────────────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_OPENAI_KEY=your_openai_key_here
AZURE_OPENAI_API_VERSION=2024-02-01
CHAT_DEPLOYMENT=gpt-4o                        # must match your deployment name in Azure
EMBED_DEPLOYMENT=text-embedding-ada-002       # must match your deployment name in Azure

# ── Storage paths (leave as-is unless you want to change folder names) ────────
INPUT_PDF_FOLDER=input_pdfs
OUTPUT_TXT_FILE=output_combined_txt/combined_output.txt
CHROMA_PERSIST_DIR=chroma_store
CHROMA_COLLECTION=gujarat_docs
CONVERSATIONS_DIR=conversation_store

# ── JWT (change this to any long random string — keep it secret) ──────────────
JWT_SECRET_KEY=my-very-secret-key-change-this-123456

# ── RAG tuning (defaults work well, adjust if needed) ────────────────────────
VECTOR_SEARCH_TOP_K=8         # number of chunks retrieved per query
MAX_HISTORY_TURNS=10          # number of past conversation turns sent to the LLM
```

> **Where to find your Azure credentials:**
> - **Document Intelligence:** Azure Portal → your DI resource → Keys and Endpoint
> - **Azure OpenAI:** Azure Portal → your OpenAI resource → Keys and Endpoint
> - **Deployment names:** Azure OpenAI Studio → Deployments tab

**2.3 — Verify your `.env` is never committed**

Make sure `.env` is listed in your `.gitignore`:

```bash
echo ".env" >> .gitignore
```

---

## Step 3 — Add Your PDFs

**3.1 — Create the input folder**

```bash
mkdir input_pdfs
```

**3.2 — Copy all 15 scanned PDFs into the folder**

```
chatbot/
└── input_pdfs/
    ├── document_1.pdf
    ├── document_2.pdf
    ├── ...
    └── document_15.pdf
```

> **Important:** The PDFs can be scanned image PDFs — Azure Document Intelligence
> handles OCR automatically. You do not need searchable/text-layer PDFs.

**3.3 — Check file names**

Avoid spaces or special characters in PDF file names. Use underscores instead:

```bash
# Bad:  Annual Report 2023-24.pdf
# Good: Annual_Report_2023-24.pdf
```

---

## Step 4 — Run the Ingestion Pipeline (One-Time)

This is the most important step. It reads all your PDFs, extracts text via OCR,
and builds the vector search index. **You only need to run this once.** If you add
new PDFs later, run it again.

```bash
python scripts/ingest_pdfs.py
```

**What this script does internally:**

```
Step 1 — OCR (Azure Document Intelligence)
  For each PDF:
    Pass 1: prebuilt-read  → extracts clean page-wise text
    Pass 2: prebuilt-layout → extracts table structure
    Output: combined_output.txt (one block per page with metadata)

Step 2 — Indexing (ChromaDB + Azure OpenAI Embeddings)
  Parses combined_output.txt into page-wise chunks
  Embeds each chunk via text-embedding-ada-002
  Stores vectors in chroma_store/ (persisted to disk)
```

**Expected terminal output:**

```
============================================================
STEP 1: OCR — Extracting text from scanned PDFs
============================================================

Processing: document_1.pdf
Processing: document_2.pdf
...
Processing: document_15.pdf

✅ Combined TXT → /path/to/output_combined_txt/combined_output.txt

============================================================
STEP 2: INDEXING — Building ChromaDB vectorstore
============================================================

[vector_service] Parsed 320 page chunks from combined_output.txt
  Embedding batch 1 / 8
  Embedding batch 2 / 8
  ...
  Embedding batch 8 / 8
[vector_service] ✅ Vectorstore built and persisted → chroma_store/gujarat_docs

✅ Ingestion complete. ChromaDB is ready.
You can now start the server: uvicorn main:app --reload
```

> **How long does it take?**
> - OCR: ~30–90 seconds per PDF (Azure DI processes scanned images)
> - Embedding: ~2–5 minutes for 15 PDFs (Azure OpenAI rate limits apply)
> - Total: roughly 15–45 minutes for 15 PDFs the first time

> **What if it stops halfway?**
> Re-run the same command. ChromaDB checks if the index already exists and skips
> re-embedding. OCR will re-run, but it is idempotent (safe to run again).

---

## Step 5 — Start the FastAPI Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected terminal output:**

```
[startup] Loading vectorstore...
[vector_service] Loading existing vectorstore from chroma_store/gujarat_docs
[startup] ✅ Vectorstore ready. Server accepting requests.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

The server is now running at: `http://localhost:8000`

Interactive API docs are available at: `http://localhost:8000/docs`

> **`--reload` flag:** Automatically restarts the server when you edit code.
> Remove this flag in production.

---

## Step 6 — Test the API

You can test using the browser Swagger UI, curl commands, or Postman.

### Option A — Swagger UI (easiest)

Open `http://localhost:8000/docs` in your browser. You will see all endpoints with
a built-in form to try them.

---

### Option B — curl (terminal)

**6.1 — Register a new user**

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ramesh Patel",
    "email": "ramesh@example.com",
    "password": "mypassword123"
  }'
```

Expected response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Save the `access_token` — you need it for all chat requests.

---

**6.2 — Login (returning user)**

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "ramesh@example.com",
    "password": "mypassword123"
  }'
```

Returns the same token structure. Use the new token for subsequent requests.

---

**6.3 — Send a chat message**

Replace `YOUR_TOKEN` with the `access_token` from step 6.1 or 6.2.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "What are the categories of ration cards in Ahmedabad?"
  }'
```

Expected response:
```json
{
  "answer": "According to the documents, in Ahmedabad city during 2011-12, ration cards are divided into four categories:\n\n- **APL-1** (Above Poverty Line 1)\n- **APL-2** (Above Poverty Line 2)\n- **BPL** (Below Poverty Line)\n- **Antyodaya** (Extremely poor families)\n\n📄 Source: [Document: Annual_Report, Page: 19]",
  "sources": [
    "Document: Annual_Report, Page: 19"
  ]
}
```

---

**6.4 — Ask a follow-up question (conversation continuity)**

Use the same token. The server automatically remembers the previous conversation.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "How many cards are in the BPL category?"
  }'
```

The bot will answer using the conversation context from the previous message.

---

**6.5 — Get conversation history**

```bash
curl -X GET http://localhost:8000/chat/history \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Returns all messages for this user — **even after server restarts**.

---

**6.6 — Clear conversation history**

```bash
curl -X DELETE http://localhost:8000/chat/history \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Wipes chat history. User account is not deleted.

---

**6.7 — Health check**

```bash
curl http://localhost:8000/health
```

Expected: `{"status": "ok"}`

---

## API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | No | Create new account |
| `POST` | `/auth/login` | No | Login, get JWT token |
| `POST` | `/chat` | ✅ JWT | Send message, get grounded answer |
| `GET` | `/chat/history` | ✅ JWT | Fetch full conversation history |
| `DELETE` | `/chat/history` | ✅ JWT | Clear conversation history |
| `GET` | `/health` | No | Server health check |

**How to send the JWT on every request:**

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Folder Structure After Setup

After running all steps, your project should look like this:

```
chatbot/
│
├── input_pdfs/                      ← Your 15 PDFs (you added these)
│   ├── document_1.pdf
│   └── ...
│
├── output_combined_txt/             ← Auto-created by Step 4
│   └── combined_output.txt          ← OCR output: all pages with metadata
│
├── chroma_store/                    ← Auto-created by Step 4
│   └── gujarat_docs/                ← Persisted vector index (ChromaDB)
│       ├── chroma.sqlite3
│       └── ...
│
├── conversation_store/              ← Auto-created on first chat
│   ├── 550e8400-e29b-41d4-a716-...json   ← User 1's conversation
│   └── 7b3f1a20-c44d-52e5-b827-...json   ← User 2's conversation
│
├── user_store/                      ← Auto-created on first register
│   └── users.json                   ← All registered users
│
└── ...rest of project files
```

---

## Troubleshooting

### ❌ `ModuleNotFoundError` on startup

```bash
# Make sure your virtual environment is activated
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

---

### ❌ `Azure DI — HttpResponseError: 401`

Your `DOC_INTEL_KEY` or `DOC_INTEL_ENDPOINT` is wrong. Double-check:

```bash
# In Azure Portal → your Document Intelligence resource → Keys and Endpoint
# Make sure the endpoint ends with a /
# Example: https://my-resource.cognitiveservices.azure.com/
```

---

### ❌ `openai.AuthenticationError`

Your `AZURE_OPENAI_KEY` is wrong, or the `CHAT_DEPLOYMENT` / `EMBED_DEPLOYMENT`
names don't match what you created in Azure OpenAI Studio.

```bash
# In Azure OpenAI Studio → Deployments tab
# Copy the exact deployment names and paste into .env
```

---

### ❌ `No page chunks found in combined_output.txt`

The OCR step didn't complete or produced an empty file. Re-run:

```bash
python scripts/ingest_pdfs.py
```

Check if your PDFs are inside `input_pdfs/` and are valid PDF files.

---

### ❌ `RateLimitError` or `429` during embedding

Azure OpenAI has per-minute token limits. The ingestion script already handles
this with automatic retry + 60-second waits. If it keeps failing:

1. Wait 5 minutes and re-run the script.
2. Consider upgrading your Azure OpenAI tier.
3. Or reduce batch size in `vector_service.py` → `BATCH = 20`.

---

### ❌ `JWT expired` or `401 Unauthorized` on chat requests

The JWT has expired (default: 24 hours). Log in again to get a fresh token:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "yourpassword"}'
```

To extend token lifetime, change `JWT_EXPIRE_MINUTES` in `.env`.

---

### ❌ Bot says "I could not find the answer" for questions that should be in the documents

This means the vector search didn't retrieve the right chunks. Try:

1. Rephrase the question with keywords that appear in the document.
2. Increase `VECTOR_SEARCH_TOP_K` in `.env` (e.g., from 8 to 12).
3. Check if the OCR extracted that page correctly in `combined_output.txt`.

---

## Production Deployment Notes

When moving from local development to production, make these changes:

**Security:**
- Set a strong, random `JWT_SECRET_KEY` (at least 32 characters).
- Restrict `allow_origins` in `main.py` to your frontend domain only.
- Store all secrets in **Azure Key Vault**, not in `.env` files.

**Performance:**
- Remove `--reload` flag from uvicorn.
- Run with multiple workers: `uvicorn main:app --workers 4`.
- Deploy Azure OpenAI and ChromaDB in the same Azure region.

**Storage:**
- Replace JSON file-based `conversation_service.py` with Azure Cosmos DB.
- Replace JSON file-based `user_store.py` with a proper database (Cosmos DB or PostgreSQL).

**Deployment:**
```bash
# Build Docker image
docker build -t gujarat-chatbot .

# Deploy to Azure Container Apps
az containerapp up --name gujarat-chatbot --resource-group my-rg --image gujarat-chatbot
```

---

## Quick Reference Card

```bash
# First-time setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in your Azure credentials
mkdir input_pdfs                # copy your 15 PDFs here

# One-time ingestion (OCR + index)
python scripts/ingest_pdfs.py

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Open API docs in browser
http://localhost:8000/docs
```
