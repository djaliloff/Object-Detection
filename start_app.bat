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

:: Set PYTHONPATH to include root AND backend_api
set "PYTHONPATH=%ROOT_DIR%;%ROOT_DIR%backend_api;%PYTHONPATH%"
set PYTHONUNBUFFERED=1

:: Check for virtual environment
if not exist "venv311\Scripts\python.exe" (
    echo [ERROR] Virtual environment 'venv311' not found!
    pause
    exit /b
)

:: 1. Start Redis (look in the local redis\ folder first)
echo [1/6] Starting Redis Server...
if exist "%ROOT_DIR%redis\redis-server.exe" (
    start "Redis Server" /d "%ROOT_DIR%redis" "%ROOT_DIR%redis\redis-server.exe" redis.windows.conf
) else (
    start "Redis Server" cmd /k "redis-server"
)
echo Waiting for Redis to be ready...
timeout /t 8 /nobreak > nul

:: 2. Start Backend API
echo [2/6] Starting Backend API...
start "Backend API" /d "%ROOT_DIR%backend_api" "%ROOT_DIR%venv311\Scripts\python.exe" main.py
timeout /t 4 /nobreak > nul

:: 3. Start Camera Gateway
echo [3/6] Starting Camera Gateway...
start "Camera Gateway" /d "%ROOT_DIR%camera_gateway" "%ROOT_DIR%venv311\Scripts\python.exe" gateway.py
timeout /t 2 /nobreak > nul

:: 4. Start AI Inference Engine
echo [4/6] Starting AI Inference Engine...
start "AI Engine" /d "%ROOT_DIR%ai_engine" "%ROOT_DIR%venv311\Scripts\python.exe" inference.py
timeout /t 5 /nobreak > nul

:: 5. Start Event Processor
echo [5/6] Starting Event Processor...
start "Event Processor" /d "%ROOT_DIR%event_processor" "%ROOT_DIR%venv311\Scripts\python.exe" processor.py
timeout /t 2 /nobreak > nul

:: 6. Start Frontend
echo [6/6] Starting Frontend Dashboard...
if exist "frontend\node_modules" (
    start "Frontend Dashboard" /d "%ROOT_DIR%frontend" cmd /k "npm run dev"
) else (
    echo [WARNING] frontend/node_modules not found. Run 'npm install' in the frontend directory.
)

echo.
echo =====================================================
echo    All services starting in separate windows.
echo    - Frontend: http://localhost:3000
echo    - API Docs: http://localhost:8000/docs
echo =====================================================
echo.
pause
