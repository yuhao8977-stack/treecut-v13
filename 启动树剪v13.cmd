@echo off
set PYTHONPATH=%~dp0src
start "" "%~dp0runtime\pythonw.exe" -m treecut.watchdog
