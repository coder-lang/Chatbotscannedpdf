# Gujarat Info Chatbot — Complete Setup Guide

A RAG-powered (Retrieval-Augmented Generation) chatbot built with FastAPI that answers
questions from scanned Gujarati Government PDF documents. Answers are strictly grounded
in the indexed documents — no hallucination. Responses are returned as HTML.

---

## Project Structure

```
Chatbot/
│
├── main.py                          ← FastAPI entry point
├── .env.example                     ← Copy to .env and fill credentials
├── requirements.txt                 ← All Python dependencies
│
├── core/
│   └── config.py                    ← All settings loaded from .env
│
├── models/
│   └── chat.py                      ← Pydantic request/response schemas
│
├── routers/
│   └── chat.py                      ← API endpoints
│
├── services/
│   ├── chat_service.py              ← Core RAG pipeline
│   ├── conversation_service.py      ← Redis-based persistent history
│   ├── vector_service.py            ← ChromaDB vector search
│   └── ocr_service.py               ← Azure Document Intelligence OCR
│
├── scripts/
│   └── ingest_pdfs.py               ← One-time setup script
│
├── input_pdfs/                      ← PUT YOUR PDFs HERE
├── output_combined_txt/             ← Auto-created after ingestion
└── chroma_store/                    ← Auto-created after ingestion
```

---

## How It Works

```
Your PDFs (input_pdfs/)
        │
        ▼  [Run ONCE — ingest_pdfs.py]
Azure Document Intelligence
        │  Dual-pass OCR: text + tables per page
        ▼
combined_output.txt
        │
        ▼
Azure OpenAI Embeddings → ChromaDB (chroma_store/)
        │
        └──────────────────────────────────────────┐
                                                   │
User sends { user_id, message }                    │
        │                                          │
        ▼                                          ▼
Year extraction from query         ChromaDB vector search (top 15 chunks)
        │                                          │
        └──────────┬────────────────────────────── ┘
                   │
                   ▼
        Year filter (remove wrong-year chunks)
                   │
                   ▼
        Redis: load conversation history + summary
                   │
                   ▼
        Azure OpenAI GPT-4o
        (temperature=0, ONLY uses retrieved context)
                   │
                   ▼
        HTML response + citations
                   │
                   ▼
        Redis: save both turns, auto-summarize if needed
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or higher |
| Redis | Local or Azure Cache for Redis |

Azure services needed:

| Service | What You Need |
|---|---|
| Azure Document Intelligence | Endpoint URL + API Key |
| Azure OpenAI | Endpoint URL + API Key + Deployment names |
| Redis | Local Redis OR Azure Cache for Redis |

---

## Step 1 — Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate — Windows
venv\Scripts\activate

# Activate — macOS / Linux
source venv/bin/activate

# Clean install (important — avoids version conflicts)
pip uninstall langchain langchain-core langchain-openai langchain-community \
    langchain-text-splitters langsmith chromadb openai httpx pydantic \
    fastapi uvicorn tiktoken redis -y

pip install -r requirements.txt

# Verify no conflicts
pip check
```

Expected: `No broken requirements`

---

## Step 2 — Configure Environment Variables

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in your values:

```env
# Azure Document Intelligence
DOC_INTEL_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
DOC_INTEL_KEY=your_key_here

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_KEY=your_key_here
AZURE_OPENAI_API_VERSION=2024-02-01
CHAT_DEPLOYMENT=gpt-4o                    ← must match Azure OpenAI Studio deployment name
EMBED_DEPLOYMENT=text-embedding-ada-002   ← must match Azure OpenAI Studio deployment name

# Redis — Azure Cache for Redis (production)
REDIS_HOST=your-redis.redis.cache.windows.net
REDIS_PORT=6380
REDIS_PASSWORD=your_redis_access_key
REDIS_SSL=true
REDIS_TTL_DAYS=30

# Redis — Local (development only)
# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_PASSWORD=
# REDIS_SSL=false

# Storage paths (leave as-is)
INPUT_PDF_FOLDER=input_pdfs
OUTPUT_TXT_FILE=output_combined_txt/combined_output.txt
CHROMA_PERSIST_DIR=chroma_store
CHROMA_COLLECTION=gujarat_docs

# RAG tuning
VECTOR_SEARCH_TOP_K=8
MAX_HISTORY_TURNS=10
```

---

## Step 3 — Add Your PDFs

```bash
mkdir input_pdfs
```

Copy all your scanned PDFs into `input_pdfs/`:

```
input_pdfs/
├── 2011.pdf
├── 2012.pdf
├── 2013.pdf
└── ...all PDFs here
```

Avoid spaces in file names. Use underscores: `Annual_Report_2014.pdf`

---

## Step 4 — Run Ingestion (One Time Only)

Run from the PROJECT ROOT folder (where main.py is):

```bash
cd C:\path\to\Chatbot      ← important: must be root, not scripts/
python scripts/ingest_pdfs.py
```

What this does:

```
Step 1 — OCR (Azure Document Intelligence)
  For each PDF:
    Pass 1: prebuilt-read   → extracts clean page-wise Gujarati text
    Pass 2: prebuilt-layout → extracts table structure
    Output: output_combined_txt/combined_output.txt

Step 2 — Indexing (ChromaDB + Azure OpenAI Embeddings)
  Parses combined_output.txt into page-wise chunks
  Embeds each chunk via text-embedding-ada-002
  Stores in chroma_store/ (persisted to disk)
```

Expected output:

```
============================================================
STEP 1: OCR — Extracting text from scanned PDFs
============================================================
Found 15 PDF(s) to process.

Processing: 2011.pdf
Processing: 2012.pdf
...

OCR complete → output_combined_txt/combined_output.txt

============================================================
STEP 2: INDEXING — Building ChromaDB vectorstore
============================================================
[vector_service] Parsed 320 chunks
  Embedding batch 1 / 8
  ...
  Embedding batch 8 / 8
[vector_service] Vectorstore built → chroma_store/gujarat_docs

Ingestion complete.
Now start the server:  python main.py
```

Duration: 15–45 minutes for 15 PDFs (Azure DI OCR + embedding time).

If Azure DI gives 403 Firewall error: run this script from an Azure VM in the
same region as your Document Intelligence resource.

---

## Step 5 — Start the Server

```bash
python main.py
```

Expected output:

```
[startup] Loading vectorstore...
[vector_service] Loading vectorstore from chroma_store/gujarat_docs
[startup] Server ready.
INFO: Uvicorn running on http://0.0.0.0:8000
```

API docs available at: http://localhost:8000/docs

---

## Step 6 — Using the API

### How user_id works

The frontend generates a `user_id` (UUID) and sends it with every request.

```
Same user_id  →  history loads and continues (even after restart/logout)  ✅
New user_id   →  fresh conversation starts automatically                   ✅
No login needed — first message auto-creates the user in Redis             ✅
```

---

### POST /chat — Send a message

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "abc-123",
    "message": "What is the 2014 ration card data for Ahmedabad?"
  }'
```

Response:
```json
{
  "answer": "<div class=\"answer\"><p>In 2014-15, the total BPL cards were <b>96,489</b>...</p><p class=\"source\">📄 Source: Document: Annual_2014, Page: 19, Year: 2014</p></div>",
  "sources": ["Document: Annual_2014, Page: 19"],
  "is_html": true
}
```

The `answer` field is HTML. Render it on your frontend with:
```javascript
document.getElementById("response").innerHTML = data.answer;

// React
<div dangerouslySetInnerHTML={{ __html: response.answer }} />
```

---

### GET /chat/exists — Check if user has history

```bash
curl "http://localhost:8000/chat/exists?user_id=abc-123"
```

Response:
```json
{
  "user_id": "abc-123",
  "has_history": true,
  "message": "Returning user — history loaded."
}
```

Use this on app startup to show "Welcome back" vs "Start new conversation".

---

### GET /chat/history — Get full conversation

```bash
curl "http://localhost:8000/chat/history?user_id=abc-123"
```

---

### DELETE /chat/history — Clear conversation

```bash
curl -X DELETE http://localhost:8000/chat/history \
  -H "Content-Type: application/json" \
  -d '{"user_id": "abc-123"}'
```

---

### GET /health — Health check

```bash
curl http://localhost:8000/health
```

Response: `{"status": "ok"}`

---

## API Reference

| Method | Endpoint | Body / Params | Description |
|---|---|---|---|
| `POST` | `/chat` | `{ user_id, message }` | Send message, get HTML answer |
| `GET` | `/chat/exists` | `?user_id=abc-123` | Check if user has history |
| `GET` | `/chat/history` | `?user_id=abc-123` | Get full conversation |
| `DELETE` | `/chat/history` | `{ user_id }` | Clear conversation |
| `GET` | `/health` | — | Server health check |

---

## Frontend CSS for HTML Responses

```css
div.answer {
  font-family: Arial, sans-serif;
  line-height: 1.6;
  padding: 12px;
}
div.answer table {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}
div.answer th,
div.answer td {
  border: 1px solid #ccc;
  padding: 8px 12px;
  text-align: left;
}
div.answer th {
  background-color: #f2f2f2;
  font-weight: bold;
}
p.source {
  color: #666;
  font-size: 0.85em;
  margin-top: 16px;
  border-top: 1px solid #eee;
  padding-top: 8px;
}
p.not-found {
  color: #c0392b;
  font-style: italic;
}
```

---

## Conversation History Design

History is stored in Redis under key `chat:<user_id>`:

```json
{
  "messages": [
    {"role": "user",      "content": "...", "timestamp": "2026-02-27T10:00:00Z"},
    {"role": "assistant", "content": "<div>...</div>", "timestamp": "2026-02-27T10:00:01Z"}
  ],
  "summary": "User asked about 2014 ration card data in Ahmedabad..."
}
```

Auto-summarization: when a conversation exceeds 40 messages, the oldest half is
compressed into a summary using GPT-4o. The summary is prepended to every future
LLM call so context is never lost even in very long conversations.

TTL: Redis key expires after `REDIS_TTL_DAYS` days of inactivity (default 30).
Any new message resets the TTL — active users never lose history.

---

## Anti-Hallucination Layers

| Layer | What It Does |
|---|---|
| Year extraction + filter | Detects year in query, removes wrong-year chunks before LLM sees them |
| Confidence gate | If no chunks retrieved, returns "not found" without calling LLM |
| Strict system prompt | LLM forbidden from using outside knowledge |
| Context labelling | Every chunk tagged with document name, page, and years present |
| Temperature = 0 | Most deterministic LLM output |
| HTML output format | Forces structured responses — reduces freeform hallucination |

---

## Troubleshooting

**403 Access denied (Azure DI Firewall)**
Run `ingest_pdfs.py` from an Azure VM in the same region as your DI resource.
Copy `chroma_store/` and `output_combined_txt/` back to your machine after.

**FileNotFoundError: combined_output.txt**
You must run `python scripts/ingest_pdfs.py` before starting the server.
Run from the project ROOT folder, not from inside scripts/.

**langchain / openai version conflicts**
Run the full clean uninstall first, then reinstall:
```bash
pip uninstall langchain langchain-core langchain-openai langchain-community \
    langchain-text-splitters openai httpx -y
pip install -r requirements.txt
pip check
```

**Redis connection refused**
For local development, start Redis first:
```bash
# Windows — download Redis from https://redis.io/download
redis-server

# macOS
brew install redis && redis-server

# Ubuntu
sudo apt install redis-server && sudo service redis start
```

**Bot gives wrong year data**
The year filter works on text matching. Make sure your PDFs contain the year
clearly written (e.g. "2014-15") in the page content, not just in the filename.

---

## Quick Reference

```bash
# First time setup
python -m venv venv
venv\Scripts\activate           # Windows
pip install -r requirements.txt
copy .env.example .env          # fill in credentials

# Add PDFs
mkdir input_pdfs
# copy your PDFs into input_pdfs/

# One-time ingestion (from project ROOT)
python scripts/ingest_pdfs.py

# Start server
python main.py

# Open API docs
http://localhost:8000/docs
```
