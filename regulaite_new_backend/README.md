# RegulAIte — AI Legal Document Analyser

Full-stack legal AI tool: FastAPI backend + Streamlit frontend powered by Claude.

## Folder Structure

```
regulaite_new_backend/
├── backend/
│   └── server.py          ← FastAPI server (PDF upload, Claude API, JSON response)
├── frontend/
│   └── app_with_backend.py ← Streamlit UI wired to the backend
├── .env.example            ← Copy to .env and add your API key
├── requirements.txt
├── start.bat               ← One-click launcher (Windows)
└── README.md
```

## Quick Start

### 1. Set up your API key
```
copy .env.example .env
```
Edit `.env` and set:
```
ANTHROPIC_API_KEY=sk-ant-...your-key-here...
SERVER_PORT=8000
```

### 2. Install dependencies
```
pip install -r requirements.txt
```

### 3. Start everything
Double-click `start.bat` — it opens two terminal windows:
- **Backend** at http://localhost:8000
- **Frontend** at http://localhost:8501

Or start manually:

**Terminal 1 — Backend:**
```
cd regulaite_new_backend
python backend/server.py
```

**Terminal 2 — Frontend:**
```
cd regulaite_new_backend
streamlit run frontend/app_with_backend.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check + model info |
| POST | `/analyse` | Upload PDF (`file`) or text (`text`) via form-data |
| POST | `/analyse/json` | Send `{"text": "..."}` as JSON body |

## How It Works

1. User uploads a PDF contract in the Streamlit sidebar
2. Streamlit POSTs the PDF bytes to `POST /analyse` on the FastAPI backend
3. FastAPI extracts text using **PyMuPDF** (in-memory, no disk writes)
4. Text is sent to **Claude** (`claude-sonnet-4-20250514`) with a structured prompt
5. Claude returns JSON with: risk score, red flags, bot debate logs, logic conflicts, auto-fixes
6. The Streamlit frontend renders all data across Dashboard, Smart Review, Compliance View pages

## No API Key? No Problem

If `ANTHROPIC_API_KEY` is not set, the backend returns realistic stub data so the UI still works for demos.

## Response Shape

```json
{
  "score": 87,
  "verdict": "High Risk",
  "summary": "...",
  "pages_analyzed": 12,
  "identified_risks": 4,
  "red_flags": [...],
  "loophole_logs": [...],
  "logic_conflicts": [...],
  "auto_fixes": [...]
}
```
