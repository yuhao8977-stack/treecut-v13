# Workbench 操作步骤（晨间包 UI 段）
1. 启动：`runtime\python.exe tools\production_workbench\server.py --port 8899`（已运行中）
2. 浏览器打开 http://127.0.0.1:8899/
3. 左侧点 Beat → 中部出现该 Beat 的 Claim 要求 + 播放区
4. 右侧候选卡：▶ 播放 = **subclip 窗口**（#t=start,end, 非整段）
5. 「替换本镜」→ 服务器持久化并跑本地基础重QA（无 qwen）；结果列表显示 PASS/WARNING/FAIL
6. 底部手动裁剪 start/end（有界）→「应用并重QA」
7. 关闭重开浏览器 → 状态保留（reports/storage/TREECUT_WORKBENCH_PROJECT_V1.json）
截图：reports/storage/ui_preview/workbench_main.png
