@echo off
rem ============================================================
rem TreeCut XHS Work Browser - launcher (V0.2 + Phase B1)
rem GBK + CRLF: safe for Chinese Windows cmd (codepage 936)
rem ============================================================
setlocal

set "RUNTIME_PY=E:\树剪整理\02_安装程序\TreeCut_v13\runtime\python.exe"
set "DATA_ROOT=E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
set "REPO_SRC=%~dp0..\src"

if not exist "%RUNTIME_PY%" (
    echo [ERROR] runtime python not found: %RUNTIME_PY%
    pause
    exit /b 1
)

set "TREECUT_DATA_ROOT=%DATA_ROOT%"
set "PYTHONPATH=%REPO_SRC%"
set "HF_HUB_OFFLINE=1"
rem Phase B1：AI 模型缓存指向 G（避免回写 C 盘）
set "HF_HOME=G:\AI\hf_cache"
set "HF_HUB_CACHE=G:\AI\hf_cache\hub"
set "OLLAMA_MODELS=G:\AI\ollama_models"

echo Starting TreeCut XHS Work Browser (Workspace B007)...
echo Data root: %TREECUT_DATA_ROOT%
echo HF cache: %HF_HOME%
"%RUNTIME_PY%" -m treecut.browser.main --workspace B007 %*

endlocal
