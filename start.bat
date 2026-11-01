@echo off
rem Starts the whole duck: Ollama, overlay server, duck brain, overlay page (full screen), Uno Q app if plugged in.
cd /d "%~dp0"

tasklist /fi "imagename eq ollama app.exe" | find /i "ollama" >nul
if errorlevel 1 (
    tasklist /fi "imagename eq ollama.exe" | find /i "ollama" >nul
    if errorlevel 1 start "Ollama" ollama serve
)

start "Duck overlay server" cmd /k python laptop\overlay_server.py
timeout /t 2 /nobreak >nul
start "Duck" cmd /k python laptop\duck_main.py

set OVERLAY=file:///%~dp0laptop/overlay.html?name=QUACKSWORTH
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
    "%ADB%" shell "arduino-app-cli app start user:duck" >nul 2>&1 || echo Uno Q app not started. Check App Lab.
)

echo.
echo Duck is starting. Talk to it. F8 = reset, F10 = stop. Close the windows to quit.
pause
