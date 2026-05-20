#!/bin/bash
# Stops all RegulAIte services started by start.sh

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}→  Stopping RegulAIte services...${NC}"

for PIDFILE in /tmp/regulaite_server.pid /tmp/regulaite_app.pid; do
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo -e "${GREEN}✓  Stopped PID $PID${NC}"
        fi
        rm -f "$PIDFILE"
    fi
done

# Also kill anything still holding our ports
for PORT in 8000 8501; do
    PID=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
    if [ -n "$PID" ]; then
        kill "$PID" 2>/dev/null || true
        echo -e "${GREEN}✓  Freed port $PORT${NC}"
    fi
done

echo -e "${GREEN}✓  Done${NC}"
