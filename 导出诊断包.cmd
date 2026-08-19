@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%runtime\python.exe" (
  echo [Error] TreeCut portable Python runtime not found.
  echo Please run this script from a complete TreeCut installation folder.
  pause
  exit /b 1
)
set "PYTHONPATH=%ROOT%src"
"%ROOT%runtime\python.exe" -m treecut.maintenance_cli --out "%ROOT%"
echo.
echo Bundle saved above. Copy the treecut_diagnostic_*.zip back to the
echo development computer so Codex can analyze this machine's state.
pause
