@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Tez Denetci kuruluyor...
where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
if not exist .venv\Scripts\python.exe (
  echo Python bulunamadi. python.org adresinden Python 3.10 veya ustunu kurun, "Add to PATH" secenegini isaretleyin.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
echo Kurulum tamam. Uygulamayi baslat.bat ile acin.
pause
