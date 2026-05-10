@echo off
TITLE Multi-Modal Surveillance Platform Stopper
echo =====================================================
echo    Stopping Multi-Modal Surveillance Platform...
echo =====================================================
echo.

echo Stopping Redis Server...
taskkill /F /FI "WINDOWTITLE eq Redis Server*" /T 2>nul

echo Stopping Backend API...
taskkill /F /FI "WINDOWTITLE eq Backend API*" /T 2>nul

echo Stopping Camera Gateway...
taskkill /F /FI "WINDOWTITLE eq Camera Gateway*" /T 2>nul

echo Stopping AI Engine...
taskkill /F /FI "WINDOWTITLE eq AI Engine*" /T 2>nul

echo Stopping Event Processor...
taskkill /F /FI "WINDOWTITLE eq Event Processor*" /T 2>nul

echo Stopping Frontend Dashboard...
taskkill /F /FI "WINDOWTITLE eq Frontend Dashboard*" /T 2>nul

echo.
echo Force-killing any process on port 8000 (Backend API)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a 2>nul
)

echo Force-killing any process on port 3000 (Frontend)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo Cleaning up any remaining Python/Node processes for this app...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM node.exe /T 2>nul

echo.
echo =====================================================
echo    All services stopped.
echo =====================================================
echo.
pause
