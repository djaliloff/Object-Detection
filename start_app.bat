@echo off
TITLE Multi-Modal Surveillance Platform Starter
SETLOCAL EnableDelayedExpansion

echo =====================================================
echo    Multi-Modal Surveillance Platform Starter
echo =====================================================
echo.

:: Set current directory
set ROOT_DIR=%~dp0
cd /d %ROOT_DIR%

:: Check for virtual environment
if not exist "venv311\Scripts\python.exe" (
    echo [ERROR] Virtual environment 'venv311' not found!
    echo Please create it first: python -m venv venv311
    pause
    exit /b
)

:: 1. Start Redis
echo [1/6] Starting Redis Server...
if exist "redis\redis-server.exe" (
    start "Redis Server" /d "%ROOT_DIR%redis" cmd /c "redis-server.exe redis.windows.conf || echo Redis might already be running"
) else (
    start "Redis Server" cmd /c "redis-server || echo Redis might already be running as a service"
)
timeout /t 2 /nobreak > nul

:: 2. Start Backend API
echo [2/6] Starting Backend API...
start "Backend API" /d "%ROOT_DIR%backend-api" cmd /k "..\venv311\Scripts\python.exe main.py"
timeout /t 3 /nobreak > nul

:: 3. Start Camera Gateway
echo [3/6] Starting Camera Gateway...
start "Camera Gateway" /d "%ROOT_DIR%camera-gateway" cmd /k "..\venv311\Scripts\python.exe gateway.py"
timeout /t 2 /nobreak > nul

:: 4. Start AI Inference Engine
echo [4/6] Starting AI Inference Engine...
start "AI Engine" /d "%ROOT_DIR%ai-engine" cmd /k "..\venv311\Scripts\python.exe inference.py"
timeout /t 5 /nobreak > nul

:: 5. Start Event Processor
echo [5/6] Starting Event Processor...
start "Event Processor" /d "%ROOT_DIR%event-processor" cmd /k "..\venv311\Scripts\python.exe processor.py"
timeout /t 2 /nobreak > nul

:: 6. Start Frontend
echo [6/6] Starting Frontend Dashboard...
if exist "frontend\node_modules" (
    start "Frontend Dashboard" /d "%ROOT_DIR%frontend" cmd /k "npm start"
) else (
    echo [WARNING] frontend/node_modules not found. 
    echo Please run 'npm install' in the frontend directory.
)

echo.
echo =====================================================
echo    All services are starting in separate windows.
echo    - Frontend: http://localhost:3000
echo    - API Docs: http://localhost:8000/docs
echo.
echo    Close the separate windows to stop services.
echo =====================================================
echo.
pause
