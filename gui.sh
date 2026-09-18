#!/bin/bash
# ==============================================================================
# Summit Checksheet Master Automation - Web GUI Launcher
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

# Activate virtual environment if present
if [ -d "$PROJECT_DIR/.venv" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

HOST="127.0.0.1"
PORT="8000"
URL="http://$HOST:$PORT"

# Check if port is already in use and free it
EXISTING_PID=$(lsof -ti :"$PORT" 2>/dev/null)
if [ -n "$EXISTING_PID" ]; then
    echo " [*] Membersihkan instance lama di port $PORT (PID: $EXISTING_PID)..."
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 0.8
fi

echo ""
echo "========================================================================"
echo "    ⚡ Summit Adyawinsa - Checksheet Master Automation Studio ⚡"
echo "========================================================================"
echo " [*] Menjalankan Web Dashboard di: $URL"
echo " [*] Tekan Ctrl+C di terminal ini untuk mematikan server."
echo "========================================================================"
echo ""

# Open browser in background after 1 second
(sleep 1.2 && open "$URL" 2>/dev/null) &

# Run FastAPI server via uvicorn with auto-reload (excluding static/uploads/data/cache directories)
python3 -m uvicorn web_app:app --host "$HOST" --port "$PORT" --reload \
    --timeout-keep-alive 5 \
    --reload-exclude "extracted_images/*" \
    --reload-exclude "documents/*" \
    --reload-exclude "logs/*" \
    --reload-exclude "data/*" \
    --reload-exclude "*.json" \
    --reload-exclude "*.log" \
    --reload-exclude ".*"
