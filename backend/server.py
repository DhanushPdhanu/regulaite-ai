"""
server.py — RegulAIte FastAPI Backend
Hacker 2 (Shashank) owns this file.

Interfaces:
- Dhanush (Hacker 1): Streamlit frontend calls all endpoints here
- Punith  (Hacker 3): agents/crew.py is imported and called here
- Ullas   (Hacker 4): schemas.py, memory/bridge.py imported here

Endpoints:
  POST /upload              → parse PDF, return clauses
  POST /analyse             → run full agent pipeline
  GET  /results/{doc_id}   → return cached analysis
  GET  /export/{doc_id}    → download redline .docx
  GET  /health             → service health check
  GET  /status             → per-module availability (Dhanush's sync banner)
"""

import os
import uuid
import json
import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
from dotenv import load_dotenv

load_dotenv()

# ── Set HuggingFace offline mode BEFORE any sentence_transformers import ──────
# This forces the model to load from local cache (~/.cache/huggingface/hub/)
# and prevents SSL certificate errors on corporate/restricted networks.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("regulaite.server")

# ── Add repo root to path so relative imports work from any working dir ───────
_REPO_ROOT = Path(__file__).parent.resolve()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── In-memory store ───────────────────────────────────────────────────────────
_doc_store:      dict = {}   # doc_id → upload result
_analysis_store: dict = {}   # doc_id → analysis result

# ── Module availability flags (set at startup) ────────────────────────────────
_PARSER_AVAILABLE  = False
_BRIDGE_AVAILABLE  = False
_AGENTS_AVAILABLE  = False
_REDLINE_AVAILABLE = False


# ── App factory ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: probe every teammate module and log availability.
    Runs ONCE when the server starts — never crashes even if a
    teammate's module is missing or broken.
    """
    global _PARSER_AVAILABLE, _BRIDGE_AVAILABLE
    global _AGENTS_AVAILABLE, _REDLINE_AVAILABLE

    log.info("=" * 55)
    log.info("RegulAIte backend starting — module availability check")
    log.info("=" * 55)

    # Probe Shashank's own parser
    try:
        from ingestion.parser import extract_clauses
        _PARSER_AVAILABLE = True
        log.info("  ✓ ingestion/parser.py       AVAILABLE")
    except Exception as e:
        log.warning("  ✗ ingestion/parser.py       MISSING  (%s)", e)

    # Probe Ullas's bridge
    try:
        from memory.bridge import run_full_analysis, get_graph_for_export
        from memory.reset_between_docs import reset_for_new_document
        _BRIDGE_AVAILABLE = True
        log.info("  ✓ memory/bridge.py          AVAILABLE")
    except Exception as e:
        log.warning("  ✗ memory/bridge.py          MISSING  (%s)", e)

    # Probe Punith's agents
    try:
        from agents.crew import analyse
        _AGENTS_AVAILABLE = True
        log.info("  ✓ agents/crew.py            AVAILABLE")
    except Exception as e:
        log.warning("  ✗ agents/crew.py            MISSING  (%s)", e)

    # Probe Shashank's redline exporter
    try:
        from export.redline import generate_redline_docx
        _REDLINE_AVAILABLE = True
        log.info("  ✓ export/redline.py         AVAILABLE")
    except Exception as e:
        log.warning("  ✗ export/redline.py         MISSING  (%s)", e)

    log.info("=" * 55)
    log.info(
        "Modules ready: parser=%s  bridge=%s  agents=%s  redline=%s",
        _PARSER_AVAILABLE, _BRIDGE_AVAILABLE,
        _AGENTS_AVAILABLE, _REDLINE_AVAILABLE,
    )
    log.info("Server ready — http://localhost:%s", os.getenv("SERVER_PORT", "8000"))
    log.info("=" * 55)
    yield
    log.info("RegulAIte backend shutting down.")


app = FastAPI(
    title="RegulAIte API",
    description="Agentic AI Legal Document Simplifier — Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Admin"])
async def health():
    """
    Returns service health + per-module availability.
    Dhanush's status banner reads this — the "status": "ok" key
    must always be present regardless of module availability.
    """
    return {
        "status":  "ok",
        "modules": {
            "parser":  _PARSER_AVAILABLE,
            "bridge":  _BRIDGE_AVAILABLE,
            "agents":  _AGENTS_AVAILABLE,
            "redline": _REDLINE_AVAILABLE,
        },
    }


# ── Upload ────────────────────────────────────────────────────────────────────

@app.post("/upload", tags=["Documents"])
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts a PDF, extracts clauses, returns clause list.
    Falls back to stub clauses if parser is unavailable.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files accepted. Please upload a .pdf file.",
        )

    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    doc_id = str(uuid.uuid4())
    log.info("Upload: %s  doc_id=%s  size=%d bytes",
             file.filename, doc_id, len(pdf_bytes))

    # Parse clauses — real or stub
    if _PARSER_AVAILABLE:
        try:
            from ingestion.parser import extract_clauses
            clauses = extract_clauses(pdf_bytes, doc_id)
            log.info("Parser extracted %d clauses from %s",
                     len(clauses), file.filename)
        except Exception as e:
            log.error("Parser failed: %s — falling back to stub", e)
            clauses = _stub_clauses(doc_id)
    else:
        log.warning("Parser unavailable — using stub clauses")
        clauses = _stub_clauses(doc_id)

    result = {
        "doc_id":       doc_id,
        "filename":     file.filename,
        "clause_count": len(clauses),
        "clauses":      clauses,
    }
    _doc_store[doc_id] = result
    log.info("Stored doc_id=%s with %d clauses", doc_id, len(clauses))
    return result


# ── Analyse ───────────────────────────────────────────────────────────────────

@app.post("/analyse", tags=["Analysis"])
async def analyse_document(body: dict):
    """
    Runs the full pipeline: bridge (Ullas) + agents (Punith).
    Merges results and caches in _analysis_store.
    Each module is called independently — one failing never
    blocks the others from running.
    """
    doc_id = body.get("doc_id")
    if not doc_id:
        raise HTTPException(
            status_code=422,
            detail="Request body must contain 'doc_id'.",
        )
    if doc_id not in _doc_store:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{doc_id}' not found. Call /upload first.",
        )

    doc         = _doc_store[doc_id]
    clauses_raw = doc.get("clauses", [])
    log.info("Analyse start: doc_id=%s  clauses=%d", doc_id, len(clauses_raw))

    # ── Step 1: Convert raw dicts → Clause objects for Ullas's tools ──────────
    clause_objects = []
    if _BRIDGE_AVAILABLE:
        try:
            from schemas import Clause
            clause_objects = [Clause(**c) for c in clauses_raw]
            log.info("Converted %d raw clauses to Clause objects",
                     len(clause_objects))
        except Exception as e:
            log.error("Clause conversion failed: %s", e)
            clause_objects = []

    # ── Step 2: Run Ullas's bridge (contradiction + RAG citation) ─────────────
    bridge_result = _stub_bridge_result(clauses_raw)
    if _BRIDGE_AVAILABLE and clause_objects:
        try:
            from memory.reset_between_docs import reset_for_new_document
            from memory.bridge import run_full_analysis
            reset_for_new_document()
            bridge_result = run_full_analysis(clause_objects)
            log.info(
                "Bridge complete: %d contradictions, hallucination_rate=%.3f",
                len(bridge_result.get("contradictions", [])),
                bridge_result.get("hallucination_rate", 0.0),
            )
        except Exception as e:
            log.error("Bridge failed: %s — using stub bridge result", e)

    # ── Step 3: Run Punith's CrewAI agents ────────────────────────────────────
    agent_result = _stub_agent_result(clauses_raw)
    if _AGENTS_AVAILABLE:
        try:
            from agents.crew import analyse
            agent_result = analyse(
                clause_objects if clause_objects else clauses_raw
            )
            log.info(
                "Agents complete: %d fixes, %d violations",
                len(agent_result.get("fixed_clauses", [])),
                len(agent_result.get("compliance_violations", [])),
            )
        except Exception as e:
            log.error("Agents failed: %s — using stub agent result", e)

    # ── Step 4: Merge all results ─────────────────────────────────────────────
    analysis = _merge_results(doc_id, doc, bridge_result, agent_result)
    _analysis_store[doc_id] = analysis
    log.info(
        "Analyse complete: doc_id=%s  score=%d  label=%s",
        doc_id,
        analysis["overall_risk_score"],
        analysis["risk_label"],
    )
    return analysis


# ── Results ───────────────────────────────────────────────────────────────────

@app.get("/results/{doc_id}", tags=["Analysis"])
async def get_results(doc_id: str):
    """
    Returns the cached analysis result for a previously analysed doc.
    Dhanush calls this on page refresh and navigation between tabs.
    """
    if doc_id not in _analysis_store:
        if doc_id in _doc_store:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Document '{doc_id}' was uploaded but not yet analysed. "
                    "Call POST /analyse first."
                ),
            )
        raise HTTPException(
            status_code=404,
            detail=f"Document '{doc_id}' not found.",
        )
    return _analysis_store[doc_id]


# ── Export ────────────────────────────────────────────────────────────────────

@app.get("/export/{doc_id}", tags=["Export"])
async def export_redline(doc_id: str):
    """
    Generates and returns a .docx redline document.
    Returns a FileResponse so the browser triggers a download.
    Returns 503 if redline.py is unavailable.
    """
    if doc_id not in _analysis_store:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No analysis found for '{doc_id}'. "
                "Run POST /analyse before exporting."
            ),
        )

    if not _REDLINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=(
                "export/redline.py is not available. "
                "Ensure python-docx is installed and the file exists."
            ),
        )

    analysis = _analysis_store[doc_id]

    try:
        from export.redline import generate_redline_docx
        docx_path = generate_redline_docx(analysis, doc_id)
        log.info("Redline generated: %s", docx_path)
    except Exception as e:
        log.error("Redline generation failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Redline generation failed: {str(e)}",
        )

    short_id = doc_id[:8]
    return FileResponse(
        path=docx_path,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        filename=f"regulaite_redline_{short_id}.docx",
        headers={
            "Content-Disposition": (
                f'attachment; filename="regulaite_redline_{short_id}.docx"'
            )
        },
    )


# ── Status ────────────────────────────────────────────────────────────────────

@app.get("/status", tags=["Admin"])
async def module_status():
    """
    Detailed module status for Dhanush's sync check banner.
    Returns per-module availability so the frontend can show
    exactly which teammate modules are loaded.
    """
    return {
        "server":  "online",
        "modules": {
            "parser": {
                "available": _PARSER_AVAILABLE,
                "owner":     "Shashank (Hacker 2)",
                "file":      "ingestion/parser.py",
            },
            "bridge": {
                "available": _BRIDGE_AVAILABLE,
                "owner":     "Ullas (Hacker 4)",
                "file":      "memory/bridge.py",
            },
            "agents": {
                "available": _AGENTS_AVAILABLE,
                "owner":     "Punith (Hacker 3)",
                "file":      "agents/crew.py",
            },
            "redline": {
                "available": _REDLINE_AVAILABLE,
                "owner":     "Shashank (Hacker 2)",
                "file":      "export/redline.py",
            },
        },
        "documents_in_memory": len(_doc_store),
        "analyses_in_memory":  len(_analysis_store),
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _merge_results(
    doc_id: str,
    doc: dict,
    bridge_result: dict,
    agent_result: dict,
) -> dict:
    """
    Merges Ullas's bridge output + Punith's agent output into the
    unified AnalysisResult schema that Dhanush's frontend reads.

    Handles both dict-style and Pydantic model_dump() output from
    teammates' modules. Produces exactly the API contract schema
    with no missing keys, even when either result is a stub.
    """
    clauses = doc.get("clauses", [])

    # ── Contradictions from Ullas's Z3 validator ──────────────────────────────
    raw_contradictions = bridge_result.get("contradictions", [])
    contradictions = []
    for c in raw_contradictions:
        if hasattr(c, "model_dump"):
            c = c.model_dump()
        contradictions.append({
            "clause_id_a":        c.get("clause_id_a", ""),
            "clause_id_b":        c.get("clause_id_b", ""),
            "contradiction_type": c.get("contradiction_type", "MUTUAL_EXCLUSION"),
            "explanation":        c.get("explanation", ""),
            "z3_proof":           c.get("z3_proof", ""),
        })

    # ── Citation results from Ullas's RAG ─────────────────────────────────────
    raw_citations = bridge_result.get("citation_results", [])
    citation_results = []
    for r in raw_citations:
        if hasattr(r, "model_dump"):
            r = r.model_dump()
        citation_results.append({
            "claim":               r.get("claim", ""),
            "source_clause_id":    r.get("source_clause_id", ""),
            "source_page":         r.get("source_page", 1),
            "source_text_excerpt": r.get("source_text_excerpt", ""),
            "confidence_score":    float(r.get("confidence_score", 0.0)),
            "verified":            bool(r.get("verified", False)),
        })

    # ── Compliance violations from Punith's agents ────────────────────────────
    raw_violations = agent_result.get("compliance_violations", [])
    compliance_violations = []
    for v in raw_violations:
        if hasattr(v, "model_dump"):
            v = v.model_dump()
        compliance_violations.append({
            "clause_id":      v.get("clause_id", ""),
            "violation_type": v.get("violation_type", "UNKNOWN"),
            "description":    v.get("description", ""),
            "severity":       v.get("severity", "MEDIUM"),
        })

    # ── Fixed clauses from Punith's agents ────────────────────────────────────
    raw_fixed = agent_result.get("fixed_clauses", [])
    fixed_clauses = []
    for f in raw_fixed:
        if hasattr(f, "model_dump"):
            f = f.model_dump()
        fixed_clauses.append({
            "clause_id":       f.get("clause_id", ""),
            "original_text":   f.get("original_text", ""),
            "fixed_text":      f.get("fixed_text", ""),
            "fix_explanation": f.get("fix_explanation", ""),
        })

    # ── Citation graph from Ullas's NetworkX tracker ──────────────────────────
    citation_graph = bridge_result.get("citation_graph", {
        "nodes": [], "edges": [], "summary": {}, "top_cited": [],
    })
    if hasattr(citation_graph, "model_dump"):
        citation_graph = citation_graph.model_dump()

    # ── Overall risk score ────────────────────────────────────────────────────
    scores = [c.get("risk_score", 0) for c in clauses if c.get("risk_score")]
    overall = int(sum(scores) / len(scores)) if scores else 0
    risk_label = (
        "CRITICAL" if overall >= 80 else
        "HIGH"     if overall >= 60 else
        "MEDIUM"   if overall >= 35 else
        "LOW"
    )

    hallucination_rate = float(bridge_result.get("hallucination_rate", 0.0))

    return {
        "doc_id":                doc_id,
        "overall_risk_score":    overall,
        "risk_label":            risk_label,
        "clauses":               clauses,
        "contradictions":        contradictions,
        "compliance_violations": compliance_violations,
        "citation_results":      citation_results,
        "fixed_clauses":         fixed_clauses,
        "hallucination_rate":    hallucination_rate,
        "citation_graph":        citation_graph,
    }


def _stub_clauses(doc_id: str) -> list:
    """Fallback clause list used when parser.py is not ready yet."""
    return [
        {
            "clause_id":     "clause_1_1",
            "clause_number": "1.1",
            "page_number":   1,
            "section":       "Liability",
            "text":          "[STUB] Liability is limited to fees paid in the last 12 months.",
            "risk_score":    82,
            "risk_reason":   "Liability cap detected — verify against other clauses.",
            "flags":         ["CONTRADICTION"],
        },
        {
            "clause_id":     "clause_1_2",
            "clause_number": "1.2",
            "page_number":   1,
            "section":       "Liability",
            "text":          "[STUB] There is no limit on liability for any damages.",
            "risk_score":    88,
            "risk_reason":   "Unlimited liability contradicts clause 1.1.",
            "flags":         ["CONTRADICTION", "ONE_SIDED"],
        },
    ]


def _stub_bridge_result(clauses_raw: list) -> dict:
    """Fallback bridge result used when Ullas's bridge.py is not ready."""
    return {
        "contradictions":     [],
        "citation_results":   [],
        "hallucination_rate": 0.0,
        "citation_graph":     {"nodes": [], "edges": [], "summary": {}, "top_cited": []},
    }


def _stub_agent_result(clauses_raw: list) -> dict:
    """Fallback agent result used when Punith's crew.py is not ready."""
    return {
        "compliance_violations": [],
        "fixed_clauses":         [],
    }


# ── OpenAPI schema export ─────────────────────────────────────────────────────

@app.get("/docs-json", tags=["Admin"], include_in_schema=False)
async def openapi_json():
    """
    Returns the raw OpenAPI schema as JSON.
    Used by Dhanush's frontend to display the API contract.
    """
    return app.openapi()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    port        = int(os.getenv("SERVER_PORT", 8000))
    host        = os.getenv("SERVER_HOST", "0.0.0.0")
    reload_flag = os.getenv("DEBUG", "true").lower() == "true"

    log.info("Starting RegulAIte API server")
    log.info("  Host:   %s", host)
    log.info("  Port:   %d", port)
    log.info("  Reload: %s", reload_flag)
    log.info("  Docs:   http://localhost:%d/docs", port)

    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=reload_flag,
        log_level="warning",
    )
