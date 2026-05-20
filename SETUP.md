# RegulAIte — Complete Setup Guide

This guide walks you through setting up RegulAIte from scratch on your machine after forking/cloning from GitHub. Follow every step in order.

---

## Prerequisites

Before you start, make sure you have:

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Python | 3.10 or higher | `python --version` |
| pip | Latest | `pip --version` |
| Git | Any | `git --version` |
| Anthropic API Key | — | Get from [console.anthropic.com](https://console.anthropic.com) |

> **Windows users:** Use PowerShell or Git Bash. The `bash start.sh` script requires Git Bash or WSL. Alternatively, run the two services manually (see Step 6b).

---

## Step 1 — Fork and Clone

### Fork (one-time, on GitHub)

1. Go to the repo on GitHub
2. Click **Fork** (top right)
3. This creates your own copy at `github.com/YOUR_USERNAME/regulaite`

### Clone to your machine

```bash
git clone https://github.com/YOUR_USERNAME/regulaite.git
cd regulaite
```

---

## Step 2 — Create a Virtual Environment

Using a virtual environment keeps your system Python clean.

```bash
# Create the environment
python -m venv .venv

# Activate it
# macOS / Linux:
source .venv/bin/activate

# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Windows (CMD):
.venv\Scripts\activate.bat
```

You should see `(.venv)` at the start of your terminal prompt.

---

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all packages. It takes 2–5 minutes the first time because it downloads:
- `sentence-transformers` (the embedding model, ~90 MB)
- `crewai` and `langchain-anthropic`
- `z3-solver` (the formal logic engine)
- `PyMuPDF` (PDF parser)

If you see errors, try:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 4 — Configure Environment Variables

```bash
cp .env.example .env
```

Now open `.env` in any text editor and fill in:

```dotenv
# Required — get from https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-...your-key-here...

# These defaults work for local development — leave them as-is
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
API_BASE_URL=http://localhost:8000
STREAMLIT_PORT=8501
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=lexai_clauses
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

> **Important:** Never commit `.env` to git. It is already in `.gitignore`.

### Demo mode (no API key)

If you don't have an Anthropic API key, the system still works in **stub mode**:
- The parser, Z3 validator, and RAG all run normally
- The CrewAI agents return pre-built stub results instead of calling the LLM
- You can still see the full UI, risk scores, and redline export

---

## Step 5 — Generate Demo Contracts

The `contracts/` folder needs 18 sample PDFs for the demo. Generate them:

```bash
python contracts/generate_contracts.py
```

This creates 18 realistic contract PDFs (SaaS agreements, NDAs, employment contracts, etc.) using `fpdf2`. Takes about 10 seconds.

---

## Step 6 — Start the Application

### Option A: One-command start (macOS / Linux / Git Bash)

```bash
bash start.sh
```

This script:
1. Loads `.env`
2. Checks Python version and dependencies
3. Checks all teammate modules
4. Generates contracts if missing
5. Kills any existing processes on ports 8000 and 8501
6. Starts the FastAPI server on port 8000
7. Waits for the server to be healthy
8. Starts the Streamlit frontend on port 8501
9. Prints the URLs

### Option B: Manual start (Windows CMD / PowerShell)

Open **two separate terminals**:

**Terminal 1 — Backend:**
```bash
cd regulaite
python server.py
```

**Terminal 2 — Frontend:**
```bash
cd regulaite
streamlit run app.py --server.port 8501
```

---

## Step 7 — Verify Everything Works

```bash
python handshake_check.py
```

All critical checks must show `✓`. Warnings (`⚠`) are non-blocking.

Expected output:
```
══ Ullas (Hacker 4) — Schemas + Validator + RAG + Bridge ──────
  ✓  schemas.py — Clause, ContradictionResult, CitationResult
  ✓  logic/validator.py — validate_clauses, extract_tags
  ✓  memory/rag.py — InMemoryRAG, citation_graph
  ✓  memory/bridge.py — all 3 CrewAI tools + run_full_analysis
  ✓  memory/reset_between_docs.py — reset_for_new_document

══ Shashank (Hacker 2) — Parser + Server + Redline ────────────
  ✓  ingestion/parser.py — extract_clauses (scored: 90/100)
  ✓  server.py — all 6 required routes present
  ✓  export/redline.py — generated 18,432 byte .docx

══ End-to-End Pipeline (offline, no server needed) ────────────
  ✓  Ullas bridge pipeline: 4 clauses → 2 contradiction(s) detected
  ✓  Parser risk scoring: all 5 test cases scored correctly
  ✓  Redline full doc: 24,576 bytes → /tmp/redline_handshake_full.docx
```

---

## Step 8 — Open the App

- **Frontend:** http://localhost:8501
- **Backend API:** http://localhost:8000
- **Swagger UI:** http://localhost:8000/docs

---

## Qdrant (Optional — for production RAG)

By default, RegulAIte uses `InMemoryRAG` — a pure-Python fallback that works without any external services. For production or large documents, you can run Qdrant:

```bash
# Using Docker
docker run -p 6333:6333 qdrant/qdrant

# Or using the Qdrant binary
# See: https://qdrant.tech/documentation/quick-start/
```

When Qdrant is running, `memory/rag.py` automatically switches to it. When it's not running, it silently falls back to `InMemoryRAG`.

---

## Stopping the Application

```bash
bash stop.sh
# or press Ctrl+C in the start.sh terminal
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'fitz'`
```bash
pip install PyMuPDF==1.24.11
```

### `ModuleNotFoundError: No module named 'z3'`
```bash
pip install z3-solver==4.13.0
```

### `Port 8000 already in use`
```bash
# Find and kill the process
# macOS/Linux:
lsof -ti tcp:8000 | xargs kill

# Windows PowerShell:
netstat -ano | findstr :8000
# Then: taskkill /PID <PID> /F
```

### `ANTHROPIC_API_KEY not set` warning
The system runs in stub mode. Agents return pre-built results. Everything else works normally.

### `sentence-transformers` download is slow
The embedding model (`all-MiniLM-L6-v2`) downloads once and is cached in `~/.cache/huggingface/`. Subsequent runs are instant.

### `contracts/` folder is empty
```bash
python contracts/generate_contracts.py
```

### Streamlit shows "API Offline"
The FastAPI server isn't running. Start it first:
```bash
python server.py
```

---

## Running Individual Modules

Each module can be run standalone for testing:

```bash
# Test the PDF parser on a specific contract
python ingestion/parser.py contracts/01_saas_subscription_agreement.pdf

# Test the Z3 contradiction detector
python logic/validator.py

# Test the RAG system (in-memory, no Qdrant needed)
python memory/rag.py

# Test the bridge (Z3 + RAG combined)
python memory/bridge.py

# Test the redline exporter (generates a sample .docx)
python export/redline.py

# Test the reset utility
python memory/reset_between_docs.py
```

---

## Environment Variables Reference

| Variable | Default | Description | Owner |
|----------|---------|-------------|-------|
| `ANTHROPIC_API_KEY` | — | Claude API key for agents | Punith |
| `SERVER_HOST` | `0.0.0.0` | FastAPI bind host | Shashank |
| `SERVER_PORT` | `8000` | FastAPI port | Shashank |
| `DEBUG` | `true` | Enable uvicorn auto-reload | Shashank |
| `API_BASE_URL` | `http://localhost:8000` | URL the frontend calls | Dhanush |
| `STREAMLIT_PORT` | `8501` | Streamlit port | Dhanush |
| `QDRANT_HOST` | `localhost` | Qdrant vector DB host | Ullas |
| `QDRANT_PORT` | `6333` | Qdrant port | Ullas |
| `QDRANT_COLLECTION` | `lexai_clauses` | Qdrant collection name | Ullas |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model | Ullas |
| `SUPABASE_URL` | — | Optional persistent storage | Shashank |
| `SUPABASE_KEY` | — | Optional persistent storage | Shashank |
