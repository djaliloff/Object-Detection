# Start all services for Multi-Modal Surveillance Platform
$ROOT = $PSScriptRoot
$PYTHON = "$ROOT\venv311\Scripts\python.exe"
$env:PYTHONPATH = "$ROOT;$ROOT\backend_api;$env:PYTHONPATH"
$env:PYTHONUNBUFFERED = "1"

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   Multi-Modal Surveillance Platform Starter" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 1. Redis
Write-Host "[1/6] Starting Redis..." -ForegroundColor Yellow
$redisExe = "$ROOT\redis\redis-server.exe"
if (Test-Path $redisExe) {
    Start-Process -FilePath $redisExe -ArgumentList "$ROOT\redis\redis.windows.conf" -WorkingDirectory "$ROOT\redis" -WindowStyle Normal
} else {
    Start-Process "cmd.exe" -ArgumentList "/k redis-server" -WindowStyle Normal
}
Write-Host "Waiting for Redis to be ready..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

# 2. Backend API
Write-Host "[2/6] Starting Backend API..." -ForegroundColor Yellow
Start-Process -FilePath $PYTHON -ArgumentList "main.py" -WorkingDirectory "$ROOT\backend_api" -WindowStyle Normal
Start-Sleep -Seconds 4

# 3. Camera Gateway
Write-Host "[3/6] Starting Camera Gateway..." -ForegroundColor Yellow
Start-Process -FilePath $PYTHON -ArgumentList "gateway.py" -WorkingDirectory "$ROOT\camera_gateway" -WindowStyle Normal
Start-Sleep -Seconds 2

# 4. AI Engine
Write-Host "[4/6] Starting AI Inference Engine..." -ForegroundColor Yellow
Start-Process -FilePath $PYTHON -ArgumentList "inference.py" -WorkingDirectory "$ROOT\ai_engine" -WindowStyle Normal
Start-Sleep -Seconds 5

# 5. Event Processor
Write-Host "[5/6] Starting Event Processor..." -ForegroundColor Yellow
Start-Process -FilePath $PYTHON -ArgumentList "processor.py" -WorkingDirectory "$ROOT\event_processor" -WindowStyle Normal
Start-Sleep -Seconds 2

# 6. Frontend
Write-Host "[6/6] Starting Frontend..." -ForegroundColor Yellow
if (Test-Path "$ROOT\frontend\node_modules") {
    Start-Process "cmd.exe" -ArgumentList "/k npm start" -WorkingDirectory "$ROOT\frontend" -WindowStyle Normal
} else {
    Write-Host "[WARNING] Run 'npm install' in frontend/ first." -ForegroundColor Red
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Green
Write-Host "   All services started!" -ForegroundColor Green
Write-Host "   Frontend : http://localhost:3000" -ForegroundColor Green
Write-Host "   API Docs : http://localhost:8000/docs" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
