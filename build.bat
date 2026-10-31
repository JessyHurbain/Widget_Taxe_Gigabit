@echo off
REM Compile un executable autonome pour Windows.
REM PyInstaller ne fait pas de compilation croisee : lancer ce script sous Windows.
setlocal
cd /d "%~dp0"

where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

if not exist .build-venv (
  %PY% -m venv .build-venv || goto :erreur
)
call .build-venv\Scripts\activate.bat

python -m pip install --quiet --upgrade pip
python -m pip install --quiet --upgrade pyinstaller psutil || goto :erreur

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller --noconfirm --clean --onefile --windowed --name TaxeGigabit taxe_gigabit.py || goto :erreur

echo.
echo Termine : dist\TaxeGigabit.exe
dir /b dist
exit /b 0

:erreur
echo Echec de la compilation.
exit /b 1
