#!/bin/bash
# ==========================================================================
#  Render build script — AI-Based Autonomous Driving System
#
#  Runs on Render's build server (Ubuntu).  Produces:
#    • frontend/dist/      (production React bundle)
#    • Python venv with    torch, ultralytics, opencv, flask, gunicorn, etc.
# ==========================================================================
set -e

echo "=== Step 1: Install system libraries for OpenCV ==="
apt-get update -qq && apt-get install -y -qq libgl1 libglib2.0-0 || {
    echo "Warning: could not install system packages via apt-get (may not be needed)."
}

echo "=== Step 2: Build the React frontend ==="
cd frontend
npm install --no-audit --no-fund
npm run build
cd ..

echo "=== Step 3: Install Python dependencies ==="
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "=== Build complete ==="
echo "Frontend bundle: $(ls frontend/dist/)"
echo "Python packages installed: $(pip list 2>/dev/null | wc -l) packages"
