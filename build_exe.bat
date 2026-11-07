@echo off
REM Builds a standalone CherryLogs.exe (no Python needed on the target PC).
cd /d "%~dp0"
if not exist .venv (
    py -3 -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || goto :error
python tools\make_icon.py || goto :error
pyinstaller --noconfirm --clean --windowed --onefile --name CherryLogs ^
    --icon assets\cherrylogs.ico main.py || goto :error
echo.
echo Done! Your app is at dist\CherryLogs.exe
pause
goto :eof
:error
echo Build failed.
pause
