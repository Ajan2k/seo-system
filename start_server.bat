@echo off
:: AI Blog Automation – Development Server Launcher
:: Correct entry point: app.main:app (NOT backend.app:app)

cd /d "%~dp0"

echo.
echo  ============================================
echo   AI Blog Automation v2.0 - Dev Server
echo  ============================================
echo   Dashboard:  http://127.0.0.1:8000
echo   API Docs:   http://127.0.0.1:8000/docs
echo  ============================================
echo.

:: Force UTF-8 for Windows to avoid cp1252 encoding errors
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: Activate venv if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Start the server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause
