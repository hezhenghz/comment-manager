@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
title Comment Manager Launcher

echo.
echo  ============================================
echo   Comment Manager  Starting...
echo  ============================================
echo.

:: Check Docker
docker info > nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Docker Desktop is not running.
    echo          Please start Docker Desktop first.
    echo.
    pause
    exit /b 1
)

:: Start database
echo  [1/4] Starting database...
docker-compose up -d db > nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to start database.
    pause
    exit /b 1
)
echo         OK
echo.

:: Check Windows Terminal
where wt > nul 2>&1
if %errorlevel% neq 0 (
    echo  [WARN] Windows Terminal not found, using separate windows.
    goto :fallback
)

:: Launch all services in one Windows Terminal window (3 tabs)
echo  [2/4] Opening Windows Terminal...
wt new-tab --title "NapCat" powershell -ExecutionPolicy Bypass -NoExit -File "%ROOT%\start-napcat.ps1" ^; new-tab --title "Backend" --startingDirectory "%ROOT%" powershell -ExecutionPolicy Bypass -NoExit -File "%ROOT%\start-backend.ps1" ^; new-tab --title "Frontend" --startingDirectory "%ROOT%\frontend" cmd /k "timeout /t 5 /nobreak >nul & npm run dev"
goto :show_urls

:fallback
echo  [2/4] Starting NapCat...
start "NapCat" cmd /k "cd /d "D:\Program Files\NapCat.44498.Shell" && napcat.quick.bat"
echo  [3/4] Starting backend...
start "Backend" powershell -ExecutionPolicy Bypass -NoExit -File "%ROOT%\start-backend.ps1"
timeout /t 4 /nobreak > nul
echo  [4/4] Starting frontend...
start "Frontend" cmd /k "cd /d "%ROOT%\frontend" && npm run dev"

:show_urls
for /f %%I in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Sort-Object PrefixLength | Select-Object -First 1).IPAddress"') do set LAN_IP=%%I

echo.
echo  ============================================
echo   Access URLs:
echo.
echo   Local  : http://localhost:5173
if defined LAN_IP (
    echo   LAN    : http://%LAN_IP%:5173
) else (
    echo   LAN    : (no LAN IP detected)
)
echo   API doc: http://localhost:8001/docs
echo  ============================================
echo.
echo  Minimize Windows Terminal to keep services running.
echo  Closing Windows Terminal will stop all services.
echo.
pause