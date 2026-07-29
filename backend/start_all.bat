@echo off
echo ===================================================
echo Starting PAi Project Offline-Ready Environment
echo ===================================================

echo [1/2] Launching Backend Server (FastAPI on Port 8000)...
start cmd /k "cd /d ""%~dp0Development Team Workflows\backend"" && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo [2/2] Launching Frontend Server (Vite on Port 5173)...
start cmd /k "cd /d ""%~dp0Development Team Workflows\frontend"" && npm run dev"

echo ---------------------------------------------------
echo Servers starting up. Access UI here:
echo 👉 http://localhost:5173
echo ---------------------------------------------------
timeout /t 5

