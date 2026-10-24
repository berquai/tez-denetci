@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Once kurulum.bat dosyasini calistirin.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\python.exe paketle.py
echo.
echo Ciktilar "cikti" klasorunde.
pause
