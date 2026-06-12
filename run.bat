@echo off
setlocal

:: ── Always run from THIS batch file's own folder ──────────────
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONPATH=%~dp0

:: Activate venv if present, otherwise use system Python
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

echo.
echo  The Generator — AI Video Maker
echo  Folder : %~dp0
echo  Open   : http://127.0.0.1:5000
echo.

:: Start server
python "%~dp0app.py"
pause
