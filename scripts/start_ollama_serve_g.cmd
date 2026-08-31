@echo off
chcp 65001 >nul
set OLLAMA_MODELS=G:\AI\ollama_models
taskkill /IM "ollama app.exe" /F >nul 2>&1
taskkill /IM "ollama.exe" /F >nul 2>&1
timeout /t 2 /nobreak >nul
echo [TreeCut] 正在启动 Ollama 服务 (模型目录: G:\AI\ollama_models) ...
start "" "C:\Users\admin\AppData\Local\Programs\Ollama\ollama.exe" serve
timeout /t 6 /nobreak >nul
ollama list
echo.
echo 若列表显示 qwen2.5vl:7b 则成功。托盘 App 启动的 serve 不读 G 盘模型，请勿用它替代本脚本。
pause
