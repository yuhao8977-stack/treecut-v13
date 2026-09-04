@echo off
set APP=%~1
if "%APP%"=="" set APP=%~dp0
set CONFIG=%APP%\runtime_data\config\remote.json
powershell -NoProfile -Command "$f='%CONFIG%'; New-Item -ItemType Directory -Path (Split-Path $f) -Force | Out-Null; @{hub_url='http://192.168.1.135:8766'; token='REPLACE_WITH_GENERATED_HUB_TOKEN'; client_id='DESKTOP-S6KSLFM-5a56c7'; interval_seconds=60; enabled=$true; auto_discover=$true; standalone=$true} | ConvertTo-Json | Set-Content $f -Encoding UTF8"
if exist "%APP%\src\__pycache__" rd /s /q "%APP%\src\__pycache__"
if exist "%APP%\runtime_data\cache\pycache" rd /s /q "%APP%\runtime_data\cache\pycache"
cd /d "%APP%"
set PYTHONPATH=src
start "" "%APP%\runtime\pythonw.exe" -m treecut.remote.agent_main
echo CONFIG_DONE
