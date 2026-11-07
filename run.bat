@echo off
REM Creates a virtual environment on first run, then starts CherryLogs.
cd /d "%~dp0"
if not exist .venv (
    echo Setting up CherryLogs for the first time...
    py -3 -m venv .venv || goto :error
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt || goto :error
) else (
    call .venv\Scripts\activate.bat
)
python main.py %*
goto :eof
:error
echo.
echo Setup failed. Make sure Python 3.10+ is installed (https://www.python.org).
pause
