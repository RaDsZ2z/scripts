@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title Banana Workbench
cd /d "%~dp0app"

set "PYTHON_CMD="
python -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
  py -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PYTHON_CMD=py"
)

if not defined PYTHON_CMD (
  echo.
  echo Failed to start: Python was not found.
  echo Install Python and make sure either python or py is available.
  pause
  exit /b 1
)

%PYTHON_CMD% -X utf8 app.py
if errorlevel 1 (
  echo.
  echo Failed to start. Install the required packages, then run:
  echo %PYTHON_CMD% -m pip install -r requirements.txt
  pause
)
