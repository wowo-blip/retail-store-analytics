@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m retail.etl
if errorlevel 1 goto :done
".venv\Scripts\python.exe" -m retail.report
:done
pause
