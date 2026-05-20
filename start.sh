#!/bin/bash
# ══════════════════════════════════════════════════════════════
# RegulAIte — Full Stack Startup Script
# Launches FastAPI backend + Streamlit frontend in the correct
# order with health checks between each step.
#
# Usage:
#   cd regulaite
#   bash start.sh
#
# What it starts:
#   1. FastAPI server  → http://localhost:8000
#   2. Streamlit app   → http://localhost:8501
#
# Logs:
#   /tmp/regulaite_server.log   ← FastAPI server output
#   /tmp/regulaite_app.log      ← Streamlit output
# ══════════════════════════════════════════════════════════════

set -e

# ── Terminal colours ──────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Resolve repo root regardless of where script is called from ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${BLUE}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}${BOLD}║         ⚖  RegulAIte Full Stack             ║${NC}"
echo -e "${BLUE}${BOLD}║   Agentic AI Legal Document Simplifier       ║${NC}"
echo -e "${BLUE}${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Step 0: Load .env ─────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠  .env not found — copying from .env.example${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${YELLOW}   Edit .env and fill in your API keys, then re-run.${NC}"
    else
        echo -e "${RED}✗  .env.example missing. Clone the repo again.${NC}"
        exit 1
    fi
fi

# Export all non-comment vars from .env
set -a
# shellcheck source=.env
source .env 2>/dev/null || true
set +a
echo -e "${GREEN}✓  .env loaded${NC}"

# ── Step 1: Check Python version ─────────────────────────────
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
    echo -e "${RED}✗  Python not found. Install Python 3.11+${NC}"
    exit 1
fi
PY_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓  Python $PY_VERSION${NC}"

# ── Step 2: Check core dependencies ──────────────────────────
echo -e "${YELLOW}→  Checking dependencies...${NC}"
$PYTHON -c "
missing = []
pkgs = [
    ('fastapi',   'fastapi'),
    ('uvicorn',   'uvicorn'),
    ('streamlit', 'streamlit'),
    ('fitz',      'PyMuPDF'),
    ('docx',      'python-docx'),
    ('plotly',    'plotly'),
    ('requests',  'requests'),
    ('dotenv',    'python-dotenv'),
]
for mod, pkg in pkgs:
    try:
        __import__(mod)
    except ImportError:
        missing.append(pkg)
if missing:
    print('MISSING: ' + ', '.join(missing))
    exit(1)
print('OK')
" || {
    echo -e "${RED}✗  Missing packages detected.${NC}"
    echo -e "${YELLOW}   Run: pip install -r requirements.txt${NC}"
    exit 1
}
echo -e "${GREEN}✓  Core dependencies present${NC}"

# ── Step 3: Check teammate modules ───────────────────────────
echo -e "${YELLOW}→  Checking teammate modules...${NC}"
$PYTHON -c "
results = {}
checks = [
    ('schemas',   'from schemas import Clause, ContradictionResult, CitationResult'),
    ('parser',    'from ingestion.parser import extract_clauses'),
    ('redline',   'from export.redline import generate_redline_docx'),
    ('bridge',    'from memory.bridge import run_full_analysis'),
    ('agents',    'from agents.crew import analyse'),
]
for name, stmt in checks:
    try:
        exec(stmt)
        results[name] = True
    except Exception as e:
        results[name] = False
for k, v in results.items():
    status = 'OK' if v else 'MISSING'
    print(f'  {status:8s} {k}')
"
echo -e "${GREEN}✓  Module check complete (see above)${NC}"

# ── Step 4: Generate demo contracts if missing ────────────────
PDF_COUNT=$(ls contracts/*.pdf 2>/dev/null | wc -l | tr -d ' ')
if [ "$PDF_COUNT" -lt 18 ]; then
    echo -e "${YELLOW}→  Generating demo contracts ($PDF_COUNT/18 found)...${NC}"
    $PYTHON contracts/generate_contracts.py
    echo -e "${GREEN}✓  18 demo contracts generated${NC}"
else
    echo -e "${GREEN}✓  $PDF_COUNT demo contracts present${NC}"
fi

# ── Step 5: Kill any existing processes on our ports ─────────
SERVER_PORT="${SERVER_PORT:-8000}"
APP_PORT="${STREAMLIT_PORT:-8501}"

for PORT in $SERVER_PORT $APP_PORT; do
    PID=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo -e "${YELLOW}→  Killing existing process on port $PORT (PID $PID)${NC}"
        kill "$PID" 2>/dev/null || true
        sleep 1
    fi
done

# ── Step 6: Start FastAPI server ──────────────────────────────
echo -e "${YELLOW}→  Starting FastAPI server on :$SERVER_PORT ...${NC}"
$PYTHON server.py \
    > /tmp/regulaite_server.log 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > /tmp/regulaite_server.pid

# Wait up to 15 seconds for server to respond
READY=false
for i in $(seq 1 15); do
    if curl -s "http://localhost:$SERVER_PORT/health" > /dev/null 2>&1; then
        READY=true
        break
    fi
    sleep 1
done

if [ "$READY" = false ]; then
    echo -e "${RED}✗  FastAPI server did not start within 15s${NC}"
    echo -e "${YELLOW}   Check logs: cat /tmp/regulaite_server.log${NC}"
    echo ""
    tail -20 /tmp/regulaite_server.log
    exit 1
fi
echo -e "${GREEN}✓  FastAPI server ready — http://localhost:$SERVER_PORT${NC}"
echo -e "${CYAN}   Swagger UI: http://localhost:$SERVER_PORT/docs${NC}"

# ── Step 7: Start Streamlit frontend ─────────────────────────
echo -e "${YELLOW}→  Starting Streamlit frontend on :$APP_PORT ...${NC}"
streamlit run app.py \
    --server.port "$APP_PORT" \
    --server.headless false \
    --browser.gatherUsageStats false \
    --theme.base dark \
    --theme.primaryColor "#2563EB" \
    --theme.backgroundColor "#0F1923" \
    --theme.secondaryBackgroundColor "#162032" \
    --theme.textColor "#F1F5F9" \
    > /tmp/regulaite_app.log 2>&1 &
APP_PID=$!
echo "$APP_PID" > /tmp/regulaite_app.pid

# Wait up to 10 seconds for Streamlit
sleep 3
if ! kill -0 "$APP_PID" 2>/dev/null; then
    echo -e "${RED}✗  Streamlit failed to start${NC}"
    echo -e "${YELLOW}   Check logs: cat /tmp/regulaite_app.log${NC}"
    tail -20 /tmp/regulaite_app.log
    exit 1
fi
echo -e "${GREEN}✓  Streamlit ready — http://localhost:$APP_PORT${NC}"

# ── Step 8: Print final status ────────────────────────────────
echo ""
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✓  RegulAIte is running!${NC}"
echo ""
echo -e "  ${CYAN}Frontend:${NC}  http://localhost:$APP_PORT"
echo -e "  ${CYAN}Backend: ${NC}  http://localhost:$SERVER_PORT"
echo -e "  ${CYAN}API Docs:${NC}  http://localhost:$SERVER_PORT/docs"
echo ""
echo -e "  ${YELLOW}Logs:${NC}"
echo -e "    Server:   tail -f /tmp/regulaite_server.log"
echo -e "    Frontend: tail -f /tmp/regulaite_app.log"
echo ""
echo -e "  Press ${RED}Ctrl+C${NC} to stop all services"
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════${NC}"
echo ""

# ── Trap Ctrl+C for clean shutdown ────────────────────────────
cleanup() {
    echo ""
    echo -e "${YELLOW}→  Shutting down RegulAIte...${NC}"
    [ -f /tmp/regulaite_server.pid ] && \
        kill "$(cat /tmp/regulaite_server.pid)" 2>/dev/null || true
    [ -f /tmp/regulaite_app.pid ] && \
        kill "$(cat /tmp/regulaite_app.pid)"    2>/dev/null || true
    rm -f /tmp/regulaite_server.pid /tmp/regulaite_app.pid
    echo -e "${GREEN}✓  All services stopped${NC}"
    exit 0
}
trap cleanup INT TERM

# Keep script alive so Ctrl+C works
wait
