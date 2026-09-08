@echo off
title AgniNetra - SIH Demo

echo.
echo ============================================================
echo                    AGNINETRA
echo              SIH 2026 DEMONSTRATION
echo ============================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found.
    echo Please create the venv first.
    pause
    exit /b 1
)

if not exist "data\processed\agninetra.duckdb" (
    echo [ERROR] AgniNetra database not found.
    echo Please run the data pipeline first.
    pause
    exit /b 1
)

echo [1/3] Database found.
echo.

set "BACKEND_READY="
set "BACKEND_REUSED="
set "BACKEND_STARTED="
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"
if not errorlevel 1 (
    echo [2/3] Backend already running.
    set "BACKEND_READY=1"
    set "BACKEND_REUSED=1"
    goto backend_ready
)

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if not errorlevel 1 (
    echo [NOTICE] Port 8000 is occupied by an unhealthy process.
    echo Stopping the stale listener...
    netstat -ano | findstr ":8000"
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /PID %%P /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

echo [2/3] Starting AgniNetra backend...
start "AgniNetra Backend" /b venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 > demo_server.log 2>&1
set "BACKEND_STARTED=1"

echo Waiting for the backend to become ready...
for /l %%i in (1,1,30) do (
    powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"
    if not errorlevel 1 (
        set "BACKEND_READY=1"
        goto backend_ready
    )
    timeout /t 1 /nobreak >nul
)

:backend_ready
if not defined BACKEND_READY (
    echo [ERROR] Backend did not become ready.
    echo Check demo_server.log for details.
    pause
    exit /b 1
)

echo.
echo [3/3] Running system health check...
venv\Scripts\python.exe data\demo_smoke_test.py

if errorlevel 1 (
    echo.
    echo [ERROR] System health check failed.
    echo Fix the issue before starting the demo.
    pause
    exit /b 1
)

echo.
echo Dashboard:
echo http://127.0.0.1:8000/dashboard/
echo.

if defined BACKEND_REUSED (
    echo Backend is already running in another process.
    echo Close that process to stop the server.
    pause
    exit /b 0
)

if defined BACKEND_STARTED (
    echo Switching to foreground server...
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /PID %%P /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

echo Press CTRL+C to stop the server.
echo.

venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
