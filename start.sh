#!/usr/bin/env bash
# ============================================================================
#   AI-Based Autonomous Driving System - one-command launcher (Linux / macOS)
#
#   Usage :  ./start.sh
#   Stop  :  Ctrl+C  (shuts down both servers)
#
#   Dashboard : http://localhost:5173
#   API       : http://localhost:5000/api/health
#
#   First run only: creates backend/venv and installs Python + npm packages
#   (the PyTorch download is the largest part and can take a few minutes).
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")"

IMPORT_CHECK="import flask, flask_cors, cv2, numpy, yaml"

# ---- 1. Python environment --------------------------------------------------
if python3 -c "$IMPORT_CHECK" >/dev/null 2>&1; then
    PY="$(command -v python3)"
    echo "[deps] system Python already has the backend packages - using it"
else
    PY="backend/venv/bin/python"
    if [ ! -x "$PY" ]; then
        echo "[deps] creating virtual environment backend/venv ..."
        python3 -m venv backend/venv
    fi
    if ! "$PY" -c "$IMPORT_CHECK" >/dev/null 2>&1; then
        echo "[deps] installing backend requirements (torch is large, be patient) ..."
        backend/venv/bin/pip install -q --upgrade pip
        backend/venv/bin/pip install -q -r backend/requirements.txt
    fi
fi

# ---- 2. Frontend dependencies -------------------------------------------------
if [ ! -d frontend/node_modules ]; then
    echo "[deps] installing frontend packages (first run only) ..."
    (cd frontend && npm install --no-audit --no-fund)
fi

# ---- 3. Start the backend -------------------------------------------------------
FRONT_PID=""
cleanup() {
    echo
    echo "[stop] shutting down ..."
    kill "$BACK_PID" 2>/dev/null
    [ -n "$FRONT_PID" ] && kill "$FRONT_PID" 2>/dev/null
    # npm/vite children can outlive their parent - free the ports as a fallback
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti -i tcp:5000 -i tcp:5173 2>/dev/null | xargs -r kill 2>/dev/null
    elif command -v fuser >/dev/null 2>&1; then
        fuser -k 5000/tcp 5173/tcp 2>/dev/null
    fi
    wait 2>/dev/null
    echo "[stop] both servers stopped."
    exit 0
}
trap cleanup INT TERM EXIT

echo "[run ] starting Flask API on http://localhost:5000 ..."
(cd backend && exec "$PY" app.py) &
BACK_PID=$!

for _ in $(seq 1 30); do
    curl -sf http://localhost:5000/api/health >/dev/null 2>&1 && break
    sleep 1
done

# ---- 4. Start the frontend --------------------------------------------------------
echo "[run ] starting React dashboard on http://localhost:5173 ..."
(cd frontend && exec npm run dev) &
FRONT_PID=$!

sleep 3
echo
echo "=================================================================="
echo "   ADAS is running"
echo "     Dashboard : http://localhost:5173"
echo "     API       : http://localhost:5000/api/health"
echo
echo "   Press Ctrl+C to stop both servers."
echo "=================================================================="
wait
