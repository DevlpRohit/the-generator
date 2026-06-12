@echo off
echo ============================================================
echo  Master AI Video Maker — Setup
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Create venv if missing
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate
call venv\Scripts\activate.bat

:: Upgrade pip silently
python -m pip install --upgrade pip -q

:: Install all dependencies
echo Installing dependencies (this may take 2-3 minutes)...
pip install -r requirements.txt

echo.
echo ============================================================
echo  Setup complete!  Run:  run.bat
echo ============================================================
pause
