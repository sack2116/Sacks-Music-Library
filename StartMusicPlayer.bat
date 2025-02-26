@echo off
cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH.
    pause
    exit
)

echo Installing required dependencies...
pip install --upgrade pip
pip install pandas mutagen dash

echo Starting Music Player...
start /min cmd /c python App.py
timeout /t 5 >nul

echo Opening Music Player UI...
start http://127.0.0.1:8050/
pause;
exit
