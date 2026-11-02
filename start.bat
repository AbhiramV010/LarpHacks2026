@echo off
rem One debug window runs everything. Enter opens the overlay, then this window minimizes and the duck runs in it.
title Duck debug
cd /d "%~dp0"

echo Starting sys and the overlay server in the background...
tasklist /fi "imagename eq ollama app.exe" | find /i "ollama" >nul
if errorlevel 1 (
    tasklist /fi "imagename eq ollama.exe" | find /i "ollama" >nul
    if errorlevel 1 start "" /b ollama serve
)
start "" /b pythonw laptop\overlay_server.py
timeout /t 3 /nobreak >nul

echo.
set /p "READY=press enter when ready to begin everything else: "

set OVERLAY=file:///%~dp0laptop/overlay.html?name=QUACK%%20OVERFLOW
set OVERLAY=%OVERLAY:\=/%

set "BROWSER="
if exist "%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe" set "BROWSER=%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"
if not defined BROWSER if exist "%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe" set "BROWSER=%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"
if not defined BROWSER if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if defined BROWSER (
    start "" "%BROWSER%" --start-fullscreen --app="%OVERLAY%"
) else (
    start "" "%OVERLAY%"
)

timeout /t 2 /nobreak >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0minimize.ps1"

set ADB=%LOCALAPPDATA%\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe
if exist "%ADB%" start "" /b "%ADB%" shell "arduino-app-cli app start user:duck" >nul 2>&1

python laptop\duck_main.py
echo.
echo Duck stopped. Press any key to close this window.
pause >nul
