@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title Banana Workbench
cd /d "%~dp0app"
python -X utf8 app.py
if errorlevel 1 (
  echo.
  echo Failed to start. Install Python, then run:
  echo python -m pip install -r requirements.txt
  pause
)
