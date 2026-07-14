@echo off
cd /d "%~dp0"
python work\htri_export_gui.py
if errorlevel 1 (
  echo.
  echo Program failed. Please send the log files under:
  echo %USERPROFILE%\Documents\HTRI_XML_Exporter\logs
)
pause
