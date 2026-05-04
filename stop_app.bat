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
echo Cleaning up any remaining Python/Node processes for this app...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM node.exe /T 2>nul

echo.
echo =====================================================
echo    All services stopped.
echo =====================================================
echo.
pause
