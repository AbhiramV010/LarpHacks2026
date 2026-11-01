@echo off
rem Starts the whole duck. Only the duck's debug window stays visible.
cd /d "%~dp0"

tasklist /fi "imagename eq ollama app.exe" | find /i "ollama" >nul
if errorlevel 1 (
    tasklist /fi "imagename eq ollama.exe" | find /i "ollama" >nul
    if errorlevel 1 start "" /b ollama serve
)

start "" pythonw laptop\overlay_server.py
timeout /t 2 /nobreak >nul
start "Duck debug" cmd /k python laptop\duck_main.py

set OVERLAY=file:///%~dp0laptop/overlay.html?name=QUACK%%20OVERFLOW
set OVERLAY=%OVERLAY:\=/%
set CHROME=
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if defined CHROME (
    start "" "%CHROME%" --start-fullscreen --app="%OVERLAY%"
) else (
    start "" "%OVERLAY%"
)

set ADB=%LOCALAPPDATA%\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe
if exist "%ADB%" (
    start "" /b "%ADB%" shell "arduino-app-cli app start user:duck" >nul 2>&1
)
