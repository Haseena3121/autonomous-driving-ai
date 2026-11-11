@echo off
REM ==========================================================================
REM   AI-Based Autonomous Driving System - one-command launcher (Windows)
REM
REM   Opens two terminal windows:
REM     1. ADAS backend   : Flask API   on http://localhost:5000
REM     2. ADAS dashboard : React app   on http://localhost:5173
REM
REM   First run only: each window creates its venv / node_modules and
REM   installs packages (the PyTorch download is the largest part).
REM   Close a window (or press Ctrl+C inside it) to stop that server.
REM ==========================================================================
echo Opening the two ADAS server windows ...

start "ADAS backend (Flask :5000)" cmd /k "cd /d %~dp0backend && if not exist venv (python -m venv venv && venv\Scripts\python -m pip install --upgrade pip && venv\Scripts\python -m pip install -r requirements.txt) && venv\Scripts\python app.py"

start "ADAS dashboard (React :5173)" cmd /k "cd /d %~dp0frontend && if not exist node_modules (npm install --no-audit --no-fund) && npm run dev"

echo.
echo   Dashboard : http://localhost:5173   (open this in your browser)
echo   API       : http://localhost:5000/api/health
echo.
echo Close the two server windows to stop the system.
