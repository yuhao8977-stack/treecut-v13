@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%runtime\python.exe" (
  echo [Error] TreeCut portable Python runtime not found.
  pause
  exit /b 1
)
set "PYTHONPATH=%ROOT%src"
"%ROOT%runtime\python.exe" -m treecut.remote.agent_main %*
pause
