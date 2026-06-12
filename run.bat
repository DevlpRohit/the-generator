@echo off
set PYTHONIOENCODING=utf-8
set PYTHONPATH=%~dp0

:: Activate venv if present, otherwise use system Python
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

echo.
echo  Master AI Video Maker
echo  Open: http://127.0.0.1:5000
echo.

python "%~dp0app.py"
pause
