# Backend Layer

**Owner:** Shashank (Hacker 2)
**Technology:** FastAPI, Uvicorn, PyMuPDF, python-docx

## Files

| File | Purpose |
|------|---------|
| `server.py` | FastAPI REST API — 6 endpoints, orchestrates the full pipeline |
| `ingestion/parser.py` | PDF clause extractor — PyMuPDF text extraction + regex segmentation + heuristic risk scoring |
| `ingestion/__init__.py` | Package marker |
| `export/redline.py` | Word document generator — 4-page redline .docx with tracked changes |
| `export/__init__.py` | Package marker |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | All 4 module availability flags |
| `GET` | `/status` | Per-module owner + file info |
| `POST` | `/upload` | Accept PDF → extract clauses → return List[Clause] |
| `POST` | `/analyse` | Run bridge + agents → merge → return AnalysisResult |
| `GET` | `/results/{doc_id}` | Return cached analysis |
| `GET` | `/export/{doc_id}` | Generate + download redline .docx |

## How to run

```bash
# From project root
python server.py
# Server starts at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

## Talks to

- `logic/` — via `memory/bridge.py` (Z3 contradiction detection)
- `memory/` — via `memory/bridge.py` (RAG citation verification)
- `ai_orchestration/agents/crew.py` — calls `analyse(clauses)`
- `schemas.py` — converts raw dicts to `Clause` objects
