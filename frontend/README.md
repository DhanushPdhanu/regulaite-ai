# Frontend Layer

**Owner:** Dhanush (Hacker 1)
**Technology:** Streamlit, Plotly, Pandas, NetworkX

## Files

| File | Purpose |
|------|---------|
| `app.py` | Complete Streamlit web UI — all 7 pages, CSS design system, API calls to backend |

## How to run

```bash
# From project root (not this folder)
streamlit run app.py --server.port 8501
```

## What it does

- Renders the dark-theme UI with custom CSS injected via `st.markdown`
- Calls `http://localhost:8000` (the backend) for all data
- Pages: Home, Upload, Agent Analysis, Risk Dashboard, Redline View, Citation Graph, History
- Checks all 4 teammates' modules are importable at startup (sync banner)

## Talks to

- `backend/server.py` — via HTTP REST calls (`POST /upload`, `POST /analyse`, `GET /results`, `GET /export`)
