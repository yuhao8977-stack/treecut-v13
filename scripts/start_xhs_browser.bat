@echo off
rem ============================================================
rem TreeCut 小红书工作浏览器 — 一键启动（V0.1.2）
rem 固定使用便携运行时 Python + 固定数据根（与已登录 B007 Profile 一致）
rem 避免：系统 Python 版本不一致 / 数据根漂移导致"新空 Profile 登录丢失"
rem ============================================================
chcp 65001 >nul
setlocal

set "RUNTIME_PY=E:\树剪整理\02_安装程序\TreeCut_v13\runtime\python.exe"
set "DATA_ROOT=E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
set "REPO_SRC=%~dp0..\src"

if not exist "%RUNTIME_PY%" (
    echo [错误] 未找到便携运行时：%RUNTIME_PY%
    echo 请修改本脚本顶部的 RUNTIME_PY 路径。
    pause
    exit /b 1
)

set "TREECUT_DATA_ROOT=%DATA_ROOT%"
set "PYTHONPATH=%REPO_SRC%"
set "HF_HUB_OFFLINE=1"

echo 启动 TreeCut 小红书工作浏览器（Workspace B007）...
echo 数据根：%TREECUT_DATA_ROOT%
"%RUNTIME_PY%" -m treecut.browser.main --workspace B007 %*

endlocal
