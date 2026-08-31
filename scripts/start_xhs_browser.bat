@echo off
rem ============================================================
rem TreeCut XHS Work Browser - launcher (V0.2)
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

echo Starting TreeCut XHS Work Browser (Workspace B007)...
echo Data root: %TREECUT_DATA_ROOT%
"%RUNTIME_PY%" -m treecut.browser.main --workspace B007 %*

endlocal
