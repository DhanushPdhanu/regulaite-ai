#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# run_local.sh — RegulAIte One-Command Local Launcher
# Starts the full stack: FastAPI backend + Streamlit frontend
#
# Usage:
#   cd regulaite
#   bash run_local.sh           # normal mode
#   bash run_local.sh --stub    # stub mode (no API key needed)
#   bash run_local.sh --stop    # kill all running processes
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# ── Config ────────────────────────────────────────────────────────────────────
FASTAPI_PORT=${FASTAPI_PORT:-8000}
STREAMLIT_PORT=${STREAMLIT_PORT:-8501}
LOG_DIR="logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN="\033[92m"; RED="\033[91m"; YELLOW="\033[93m"
BOLD="\033[1m";   RESET="\033[0m"

ok()   { echo -e "  ${GREEN}[OK]${RESET}  $1"; }
err()  { echo -e "  ${RED}[ERR]${RESET} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${RESET} $1"; }
info() { echo -e "  ${BOLD}$1${RESET}"; }

# ── Stop mode ─────────────────────────────────────────────────────────────────
if [[ "$1" == "--stop" ]]; then
    echo -e "\n${BOLD}Stopping RegulAIte processes...${RESET}"
    pkill -f "uvicorn server:app"   2>/dev/null && ok "FastAPI stopped"   || warn "FastAPI was not running"
    pkill -f "streamlit run app.py" 2>/dev/null && ok "Streamlit stopped" || warn "Streamlit was not running"
    echo ""
    exit 0
fi

# ── Stub mode ─────────────────────────────────────────────────────────────────
STUB_MODE=false
if [[ "$1" == "--stub" ]]; then
    STUB_MODE=true
    warn "Running in STUB MODE — LLM agents disabled, deterministic results only"
    export ANTHROPIC_API_KEY="stub_key_no_llm"
fi

echo -e "\n${BOLD}══════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  RegulAIte — Local Stack Launcher${RESET}"
echo -e "${BOLD}══════════════════════════════════════════════════════${RESET}\n"

# ── Must run from regulaite/ ──────────────────────────────────────────────────
if [[ ! -f "agents/crew.py" ]]; then
    err "Run this script from the regulaite/ directory."
    echo "    cd regulaite && bash run_local.sh"
    exit 1
fi

# ── Load .env ─────────────────────────────────────────────────────────────────
if [[ -f ".env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    ok ".env loaded"
else
    warn ".env not found — using environment defaults"
    warn "Copy .env.example to .env and fill in ANTHROPIC_API_KEY"
fi

# ── Pre-flight health check ───────────────────────────────────────────────────
info "Running pre-flight health check..."
python healthcheck.py
HEALTH_EXIT=$?
if [[ $HEALTH_EXIT -ne 0 ]]; then
    err "Health check failed with $HEALTH_EXIT blocker(s). Fix above errors first."
    exit 1
fi

# ── Create log directory ──────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"

# ── Kill any existing instances ───────────────────────────────────────────────
pkill -f "uvicorn server:app"   2>/dev/null || true
pkill -f "streamlit run app.py" 2>/dev/null || true
sleep 1

# ── Launch FastAPI backend (Shashank) ─────────────────────────────────────────
info "Starting FastAPI backend (Shashank) on port $FASTAPI_PORT..."
uvicorn server:app \
    --host 0.0.0.0 \
    --port "$FASTAPI_PORT" \
    --reload \
    > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Wait for backend to be ready (up to 15s)
echo -n "  Waiting for backend"
for i in $(seq 1 15); do
    sleep 1
    echo -n "."
    if curl -sf "http://localhost:$FASTAPI_PORT/health" > /dev/null 2>&1; then
        echo ""
        ok "Backend ready at http://localhost:$FASTAPI_PORT"
        break
    fi
    if [[ $i -eq 15 ]]; then
        echo ""
        warn "Backend did not respond within 15s. Check $BACKEND_LOG"
        warn "Launching frontend anyway..."
    fi
done

# ── Launch Streamlit frontend (Dhanush) ───────────────────────────────────────
info "Starting Streamlit frontend (Dhanush) on port $STREAMLIT_PORT..."
BACKEND_URL="http://localhost:$FASTAPI_PORT" \
streamlit run app.py \
    --server.port "$STREAMLIT_PORT" \
    --server.headless true \
    > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
sleep 3

# ── Status summary ────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  RegulAIte is running!${RESET}"
echo -e "${BOLD}══════════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BOLD}Frontend  →${RESET}  http://localhost:$STREAMLIT_PORT"
echo -e "  ${BOLD}Backend   →${RESET}  http://localhost:$FASTAPI_PORT"
echo -e "  ${BOLD}API Docs  →${RESET}  http://localhost:$FASTAPI_PORT/docs"
echo ""
echo -e "  Backend PID  : $BACKEND_PID  (logs: $BACKEND_LOG)"
echo -e "  Frontend PID : $FRONTEND_PID (logs: $FRONTEND_LOG)"
echo ""
if [[ "$STUB_MODE" == "true" ]]; then
    echo -e "  ${YELLOW}STUB MODE ACTIVE — set ANTHROPIC_API_KEY in .env for full LLM mode${RESET}"
fi
echo -e "  Stop all:   bash run_local.sh --stop"
echo -e "  Test suite: python -m pytest tests/test_crew_unit.py -v"
echo ""
echo -e "${BOLD}══════════════════════════════════════════════════════${RESET}"

# ── Tail logs ─────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}Live logs (Ctrl+C to detach — services keep running):${RESET}\n"
tail -f "$BACKEND_LOG" "$FRONTEND_LOG"
