@echo off
cd /d "%~dp0"

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo PyInstaller is not installed.
  echo Install it with: python -m pip install pyinstaller
  pause
  exit /b 1
)

python -m PyInstaller ^
  --name "HTRI_XML_Exporter" ^
  --windowed ^
  --onedir ^
  --add-data "work;work" ^
  work\htri_export_gui.py

echo Build finished: dist\HTRI_XML_Exporter
pause
