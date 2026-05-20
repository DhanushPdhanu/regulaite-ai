# RegulAIte ⚖️

> **Agentic AI Legal Document Simplifier**
> Built at HackIndia 2025 — Team Tattvasphere

---

## What is RegulAIte?

RegulAIte is a full-stack AI system that reads legal contracts (PDFs) and automatically:

1. **Extracts every clause** from the document
2. **Detects hidden contradictions** between clauses using the Z3 formal logic solver
3. **Scores each clause for risk** using pattern matching + a CrewAI LLM agent pipeline
4. **Checks for GDPR, Indian labour law, and IP violations** with exact legal citations
5. **Auto-rewrites dangerous clauses** into balanced, legally sound language
6. **Verifies every AI claim** against the actual contract text using RAG (no hallucinations)
7. **Exports a professional redline Word document** with tracked changes

Think of it as a tireless junior lawyer that reads the whole contract in 30 seconds, flags every landmine, and hands you a clean rewrite — with proof.

---

## The Problem It Solves

Most people sign contracts without reading them. Even those who do read them miss:

- **Contradictions** — Clause 3.1 caps liability at 12 months fees. Clause 3.2 says "no limit on liability." Both can't be true. Which one wins in court?
- **Auto-renewal traps** — "This agreement auto-renews unless cancelled 3 days before expiry." Three days. Most people miss it.
- **GDPR violations** — "We share your data with third-party analytics partners." No consent basis stated. That's a €20M fine.
- **One-sided clauses** — "We may modify this agreement at any time without notice." You have no recourse.
- **IP traps** — "You assign all intellectual property regardless of when it was created." That includes your side projects.

RegulAIte catches all of these automatically.

---

## Project Structure

```
regulaite/
│
├── frontend/                    ← LAYER 1: UI (Dhanush)
│   ├── app.py                   ← Streamlit web app (reference copy)
│   └── README.md
│
├── backend/                     ← LAYER 2: API + Parsing + Export (Shashank)
│   ├── server.py                ← FastAPI REST server (reference copy)
│   ├── ingestion/
│   │   └── parser.py            ← PDF clause extractor
│   ├── export/
│   │   └── redline.py           ← Word document generator
│   └── README.md
│
├── ai_orchestration/            ← LAYER 3: AI Agents (Punith)
│   ├── agents/
│   │   └── crew.py              ← CrewAI 3-agent pipeline
│   └── README.md
│
├── logic/                       ← LAYER 4: Formal Logic (Ullas)
│   ├── validator.py             ← Z3 SMT contradiction detector
│   └── README.md
│
├── memory/                      ← LAYER 5: RAG + Vector Search (Ullas)
│   ├── rag.py                   ← SentenceTransformers + Qdrant/InMemoryRAG
│   ├── bridge.py                ← CrewAI tool wrappers + plain functions
│   ├── reset_between_docs.py    ← State reset between analyses
│   └── README.md
│
├── schemas.py                   ← Shared data contracts (Ullas) — used by ALL layers
├── contracts/                   ← 18 demo PDF contracts
├── tests/                       ← Unit + integration tests
│
│   ── Entry points (run from root) ──
├── app.py                       ← `streamlit run app.py`
├── server.py                    ← `python server.py`
├── requirements.txt
├── .env.example
└── .gitignore
```

> **Note:** `frontend/`, `backend/`, `ai_orchestration/` contain reference copies of the
> source files for documentation clarity. The **live entry points** (`app.py`, `server.py`)
> remain at the project root so all relative imports resolve correctly.

## Architecture Flow

```
PDF Upload (Dhanush — frontend/app.py)
        │  HTTP POST /upload
        ▼
backend/server.py  POST /upload
        │  calls
        ▼
backend/ingestion/parser.py     ← PyMuPDF + regex + heuristic scoring
        │  returns List[Clause]
        ▼
backend/server.py  POST /analyse
        │  calls
        ├──► memory/bridge.py   ← Z3 contradictions + RAG citation check (Ullas)
        │         └── logic/validator.py  ← Z3 SMT solver
        │         └── memory/rag.py       ← SentenceTransformers + Qdrant
        │
        └──► ai_orchestration/agents/crew.py  ← CrewAI pipeline (Punith)
                   RiskAgent → ComplianceAgent → FixerAgent
        │
        ▼
backend/server.py  _merge_results()   ← unified AnalysisResult
        │
        ├──► GET /results/{doc_id}  ──►  frontend/app.py Risk Dashboard
        └──► GET /export/{doc_id}   ──►  backend/export/redline.py → .docx
```

---

## Team & Ownership

| Member | Role | Files Owned |
|--------|------|-------------|
| **Dhanush** (H1) | Frontend | `app.py` |
| **Shashank** (H2) | Backend | `server.py`, `ingestion/parser.py`, `export/redline.py` |
| **Punith** (H3) | AI Agents | `agents/crew.py` |
| **Ullas** (H4) | AI Core | `schemas.py`, `logic/validator.py`, `memory/rag.py`, `memory/bridge.py`, `memory/reset_between_docs.py`, `contracts/generate_contracts.py` |

---

## Key Technologies

| Technology | What It Does | Used In |
|------------|-------------|---------|
| **FastAPI** | REST API server | `server.py` |
| **Streamlit** | Interactive web UI | `app.py` |
| **PyMuPDF (fitz)** | PDF text extraction | `ingestion/parser.py` |
| **Z3 SMT Solver** | Formal logic contradiction detection | `logic/validator.py` |
| **CrewAI** | Multi-agent orchestration framework | `agents/crew.py` |
| **Claude (Anthropic)** | LLM for risk scoring and clause rewriting | `agents/crew.py` |
| **SentenceTransformers** | Semantic embedding for RAG | `memory/rag.py` |
| **Qdrant** | Vector database for clause retrieval | `memory/rag.py` |
| **NetworkX** | Citation graph tracking | `memory/rag.py` |
| **python-docx** | Word document generation | `export/redline.py` |
| **Pydantic** | Data validation and schemas | `schemas.py` |

---

## API Endpoints

| Method | Path | Description | Owner |
|--------|------|-------------|-------|
| `GET` | `/health` | Service health + module availability | Shashank |
| `GET` | `/status` | Per-module status for frontend banner | Shashank |
| `POST` | `/upload` | Upload PDF, extract clauses | Shashank |
| `POST` | `/analyse` | Run full agent pipeline | Shashank |
| `GET` | `/results/{doc_id}` | Get cached analysis | Shashank |
| `GET` | `/export/{doc_id}` | Download redline .docx | Shashank |
| `GET` | `/docs` | Swagger UI | FastAPI auto |

---

## Demo Flow

1. Open `http://localhost:8501`
2. Upload any PDF from the `contracts/` folder
3. Click **Analyse** — agents run in ~30 seconds
4. View the risk dashboard, contradiction graph, and compliance violations
5. Click **Download Redline** to get the tracked-changes `.docx`

---

## Quick Start

```bash
git clone https://github.com/your-org/regulaite.git
cd regulaite
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY
python contracts/generate_contracts.py
bash start.sh
```

Full setup instructions are in [SETUP.md](SETUP.md).

---

## Correctness Properties

RegulAIte is built with formal correctness in mind:

1. **No hallucinations** — every agent claim is verified against the source document via RAG. If the claim isn't grounded in the contract, `verified=False` is returned and the hallucination rate metric increases.
2. **Contradiction soundness** — Z3 only reports a contradiction when it can prove UNSAT (both assertions cannot simultaneously hold). No false positives from pattern matching alone.
3. **Graceful degradation** — if any teammate module fails to import, the server continues running with stub results. The frontend shows which modules are offline.
4. **Idempotent IDs** — clause IDs are derived from clause numbers (`clause_3_1`), not random UUIDs, so re-uploading the same document produces the same IDs.

---

## Running Tests

```bash
# Pre-demo integration check (all modules, no server needed)
python handshake_check.py

# Pre-flight environment check
python healthcheck.py

# Integration tests (requires server running)
python test_integration.py

# Unit tests
pytest tests/
```

---

## Stopping the Server

```bash
bash stop.sh
# or press Ctrl+C in the start.sh terminal
```

---

*RegulAIte — Because every contract has a landmine.*
