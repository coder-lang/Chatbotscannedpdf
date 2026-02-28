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
│   └── chat.py                      ← All API endpoints
│
├── services/
│   ├── chat_service.py              ← Core RAG pipeline (year filter + HTML output)
│   ├── conversation_service.py      ← JSON file-based persistent history
│   ├── vector_service.py            ← ChromaDB vector search
│   └── ocr_service.py               ← Azure Document Intelligence dual-pass OCR
│
├── scripts/
│   └── ingest_pdfs.py               ← One-time setup: OCR + build vector index
│
├── input_pdfs/                      ← PUT YOUR PDFs HERE
├── output_combined_txt/             ← Auto-created: combined_output.txt
├── chroma_store/                    ← Auto-created: ChromaDB vector index
└── conversation_store/              ← Auto-created: one JSON file per user_id
```

---

## How It Works

```
Your PDFs (input_pdfs/)
        │
        ▼  [Run ONCE — scripts/ingest_pdfs.py]
Azure Document Intelligence
        │  Dual-pass OCR per page:
        │    Pass 1 (prebuilt-read)   → clean Gujarati text
        │    Pass 2 (prebuilt-layout) → table structure
        ▼
output_combined_txt/combined_output.txt
        │
        ▼
Azure OpenAI Embeddings → ChromaDB (chroma_store/)
        │
        └─────────────────────────────────────────────┐
                                                      │
User sends { user_id, message }                       │
        │                                             │
        ▼                                             ▼
Extract years from query              Vector search (top 15 chunks)
        │                                             │
        └──────────────┬──────────────────────────────┘
                       │
                       ▼
          Filter chunks by requested year
          (removes wrong-year results)
                       │
                       ▼
          Load history from conversation_store/<user_id>.json
                       │
                       ▼
          Azure OpenAI GPT-4o
          (temperature=0, ONLY uses retrieved context)
                       │
                       ▼
          HTML response + citations
                       │
                       ▼
          Save both turns to conversation_store/<user_id>.json
          Auto-summarize if conversation is getting long
```

---

## Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Python | 3.10 or higher | `python --version` |
| pip | latest | `pip --version` |

Azure services needed:

| Service | What You Need |
|---|---|
| Azure Document Intelligence | Endpoint URL + API Key |
| Azure OpenAI | Endpoint URL + API Key + two deployment names |

> Make sure Azure OpenAI has two deployments:
> one for `gpt-4o` and one for `text-embedding-ada-002`

No Redis, no database, no external services beyond Azure.

---

## Step 1 — Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate — Windows
venv\Scripts\activate

# Activate — macOS / Linux
source venv/bin/activate

# Install all packages
pip install -r requirements.txt

# Verify no conflicts
pip check
```

Expected output of `pip check`: `No broken requirements`

If you see version conflicts, run a clean reinstall:

```bash
pip uninstall langchain langchain-core langchain-openai langchain-community \
    langchain-text-splitters langsmith chromadb openai httpx \
    pydantic fastapi uvicorn tiktoken -y

pip install -r requirements.txt
pip check
```

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
# Found in: Azure Portal → your DI resource → Keys and Endpoint
DOC_INTEL_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
DOC_INTEL_KEY=your_document_intelligence_key

# Azure OpenAI
# Found in: Azure Portal → your OpenAI resource → Keys and Endpoint
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_KEY=your_openai_key
AZURE_OPENAI_API_VERSION=2024-02-01

# Deployment names — must match exactly what you named them in Azure OpenAI Studio
CHAT_DEPLOYMENT=gpt-4o
EMBED_DEPLOYMENT=text-embedding-ada-002

# Storage paths — leave these as-is
INPUT_PDF_FOLDER=input_pdfs
OUTPUT_TXT_FILE=output_combined_txt/combined_output.txt
CHROMA_PERSIST_DIR=chroma_store
CHROMA_COLLECTION=gujarat_docs
CONVERSATIONS_DIR=conversation_store

# RAG tuning — adjust if needed
VECTOR_SEARCH_TOP_K=8
MAX_HISTORY_TURNS=10
```

> Make sure `.env` is in your `.gitignore` — never commit your keys.

---

## Step 3 — Add Your PDFs

Create the input folder and copy all your scanned PDFs into it:

```bash
mkdir input_pdfs
```

```
input_pdfs/
├── 2011.pdf
├── 2012.pdf
├── 2013.pdf
├── 2014.pdf
└── ...all PDFs here
```

Tips:
- Avoid spaces in file names — use underscores: `Annual_Report_2014.pdf`
- PDFs can be scanned image PDFs — Azure DI handles OCR automatically
- The file name becomes the document name shown in citations

---

## Step 4 — Run Ingestion (One Time Only)

> IMPORTANT: Run this from the PROJECT ROOT folder (where `main.py` is),
> NOT from inside the `scripts/` folder.

```bash
# Make sure you are in the root folder
cd "C:\Users\...\Chatbot"

# Verify you see main.py here
dir

# Run ingestion
python scripts/ingest_pdfs.py
```

What this does:

```
STEP 1 — OCR (Azure Document Intelligence)
  For each PDF in input_pdfs/:
    Pass 1: prebuilt-read   → extracts clean page-wise text + Gujarati digits normalized
    Pass 2: prebuilt-layout → extracts table structure per page
  Output: output_combined_txt/combined_output.txt

STEP 2 — INDEXING (ChromaDB + Azure OpenAI Embeddings)
  Parses combined_output.txt into one chunk per page
  Embeds each chunk using text-embedding-ada-002
  Saves vector index to chroma_store/
```

Expected terminal output:

```
============================================================
STEP 1: OCR — Extracting text from scanned PDFs
============================================================
Found 15 PDF(s) to process.

Processing: 2011.pdf
Processing: 2012.pdf
...
Processing: 2015.pdf

OCR complete → output_combined_txt/combined_output.txt

============================================================
STEP 2: INDEXING — Building ChromaDB vectorstore
============================================================
[vector_service] Parsed 320 chunks from combined_output.txt
  Embedding batch 1 / 8
  Embedding batch 2 / 8
  ...
  Embedding batch 8 / 8
[vector_service] Vectorstore built → chroma_store/gujarat_docs

Ingestion complete.
Now start the server:  python main.py
```

Duration: 15–45 minutes for 15 PDFs depending on Azure DI speed.

> If you get a 403 Firewall error from Azure Document Intelligence,
> run this script from an Azure VM in the same region as your DI resource.
> Copy `output_combined_txt/` and `chroma_store/` back to your machine after.
> See Troubleshooting section for details.

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
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Interactive API docs: `http://localhost:8000/docs`

---

## Step 6 — Using the API

### How user_id works

The frontend generates a `user_id` (any UUID string) and sends it with every request.
No registration or login needed.

```
Same user_id  →  loads conversation_store/<user_id>.json  →  history continues  ✅
New user_id   →  creates new .json file                   →  fresh start        ✅
Server restart →  .json files survive on disk             →  history persists   ✅
Different user →  different .json file                    →  fully isolated     ✅
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
  "answer": "<div class=\"answer\"><p>In 2014-15, the total BPL ration cards in Ahmedabad were <b>96,489</b>.</p><table><thead><tr><th>Category</th><th>Cards</th></tr></thead><tbody><tr><td>APL-1</td><td>63,942</td></tr><tr><td>BPL</td><td>96,489</td></tr></tbody></table><p class=\"source\">📄 Source: Document: Annual_2014, Page: 19, Year: 2014</p></div>",
  "sources": ["Document: Annual_2014, Page: 19"],
  "is_html": true
}
```

The `answer` field is HTML. Render it on your frontend:

```javascript
// Plain JavaScript
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

Call this on app startup to show "Welcome back" vs "Start new conversation".

---

### GET /chat/history — Get full conversation

```bash
curl "http://localhost:8000/chat/history?user_id=abc-123"
```

Response:
```json
{
  "user_id": "abc-123",
  "messages": [
    {"role": "user",      "content": "What is 2014 ration card data?", "timestamp": "..."},
    {"role": "assistant", "content": "<div class=\"answer\">...</div>", "timestamp": "..."}
  ]
}
```

---

### DELETE /chat/history — Clear conversation

```bash
curl -X DELETE http://localhost:8000/chat/history \
  -H "Content-Type: application/json" \
  -d '{"user_id": "abc-123"}'
```

Deletes `conversation_store/abc-123.json`. The user_id can be reused — next
message will start a fresh conversation.

---

### GET /health — Health check

```bash
curl http://localhost:8000/health
```

Response: `{"status": "ok"}`

---

## API Reference

| Method | Endpoint | Body / Query Param | Description |
|---|---|---|---|
| `POST` | `/chat` | `{ user_id, message }` | Send message, get HTML answer |
| `GET` | `/chat/exists` | `?user_id=abc-123` | Check if user has existing history |
| `GET` | `/chat/history` | `?user_id=abc-123` | Get full conversation history |
| `DELETE` | `/chat/history` | `{ user_id }` | Clear conversation history |
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

Each user gets one JSON file: `conversation_store/<user_id>.json`

```json
{
  "messages": [
    {"role": "user",      "content": "...", "timestamp": "2026-02-27T10:00:00Z"},
    {"role": "assistant", "content": "<div>...</div>", "timestamp": "2026-02-27T10:00:01Z"}
  ],
  "summary": "User asked about 2014 ration card data in Ahmedabad. Bot returned BPL count of 96,489."
}
```

Auto-summarization: when conversation exceeds 40 messages, the oldest half is
compressed into a summary by GPT-4o. The summary is prepended to every future
LLM call as context — so the bot always remembers earlier topics even in very
long conversations without hitting token limits.

---

## Anti-Hallucination Layers

| Layer | What It Does |
|---|---|
| Year extraction | Detects year(s) mentioned in query e.g. "2014", "2013-14" |
| Year filter | Removes chunks not containing the requested year before LLM sees them |
| Confidence gate | If no chunks retrieved, returns "not found" — LLM never called |
| Strict system prompt | LLM explicitly forbidden from using outside knowledge |
| Context labelling | Every chunk tagged with document name, page number, and years present |
| Temperature = 0 | Most deterministic LLM output possible |
| HTML output | Structured format reduces freeform hallucination |

---

## Troubleshooting

**403 Access denied due to Virtual Network/Firewall rules**

Azure Document Intelligence is blocking requests from your machine.
Fix: Run ingestion from an Azure VM in the same region as your DI resource.

```bash
# On Azure VM — run ingestion
python scripts/ingest_pdfs.py

# After it completes, copy these two folders back to your laptop:
#   output_combined_txt/
#   chroma_store/

# Then on your laptop — start the server normally
python main.py
```

---

**FileNotFoundError: combined_output.txt**

You haven't run ingestion yet, or ran it from the wrong folder.

```bash
# Must run from PROJECT ROOT (where main.py is)
cd "C:\Users\...\Chatbot"
python scripts/ingest_pdfs.py
```

---

**FileNotFoundError: input_pdfs**

Same issue — running from inside `scripts/` folder instead of root.

```bash
cd "C:\Users\...\Chatbot"   ← go to ROOT first
python scripts/ingest_pdfs.py
```

---

**Missing required env vars on startup**

Your `.env` file has wrong variable names or is missing entries.
Required names (must match exactly):

```
DOC_INTEL_ENDPOINT
DOC_INTEL_KEY
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_KEY
AZURE_OPENAI_API_VERSION
CHAT_DEPLOYMENT
EMBED_DEPLOYMENT
```

---

**Version conflict errors during pip install**

Run full clean reinstall:

```bash
pip uninstall langchain langchain-core langchain-openai langchain-community \
    langchain-text-splitters langsmith chromadb openai httpx \
    pydantic fastapi uvicorn tiktoken -y

pip install -r requirements.txt
pip check
```

---

**Bot returns wrong year data (e.g. asking 2014, getting 2011)**

The year filter works by looking for the year string inside chunk text.
Make sure your PDFs contain the year clearly written in the page content
(e.g. "2014-15" or "વર્ષ 2014"), not just in the filename.

---

**Bot says "I could not find the answer" for a question that should be in the docs**

Two possible causes:
1. Vector search didn't retrieve the right chunks — try rephrasing with keywords from the document.
2. Increase `VECTOR_SEARCH_TOP_K` in `.env` from `8` to `12` or `15`.

---

## Folder Structure After Full Setup

```
Chatbot/
├── input_pdfs/
│   ├── 2011.pdf
│   └── ...your PDFs
│
├── output_combined_txt/
│   └── combined_output.txt          ← created by ingest_pdfs.py
│
├── chroma_store/
│   └── gujarat_docs/
│       ├── chroma.sqlite3           ← created by ingest_pdfs.py
│       └── ...
│
├── conversation_store/
│   ├── abc-123.json                 ← created on first message from user abc-123
│   └── xyz-456.json                 ← created on first message from user xyz-456
│
└── ...all code files
```

---

## Quick Reference

```bash
# First time setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        ← fill in your Azure credentials

# Add PDFs
mkdir input_pdfs
# copy your PDFs into input_pdfs/

# One-time ingestion — run from project ROOT
python scripts/ingest_pdfs.py

# Start server
python main.py

# API docs
http://localhost:8000/docs
```
