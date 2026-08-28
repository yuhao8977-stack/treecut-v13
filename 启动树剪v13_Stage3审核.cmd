@echo off
rem TreeCut v13 - Stage3 Review launcher (repo code + batch1 data + dsh_models)
rem Ensures Review Center uses latest code with TARGETED_REVIEW_STAGE3_V3_1
set PYTHONPATH=C:\Users\admin\github\treecut-v13\src
set TREECUT_DATA_ROOT=E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1
set TREECUT_MODEL_ROOT=C:\Users\admin\dsh_models
set HF_HUB_OFFLINE=1
start "" "E:\树剪整理\02_安装程序\TreeCut_v13\runtime\pythonw.exe" -m treecut.desktop
