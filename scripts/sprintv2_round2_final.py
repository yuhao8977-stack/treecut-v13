# -*- coding: utf-8 -*-
"""追加本轮诚实更新到 G2 报告与主报告; 落 UI 步骤说明。"""
import sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")

upd_g2 = f"""
## 更新（{time.strftime('%Y-%m-%d %H:%M')}）— 方向复核与证据强度

- 对已检出动作窗的 6 素材在动作时刻做 EXTEND-vs-RETRACT 独立复核：2482/2483/2484/1984 → **STATIC**，1985/1986 → EXTEND
- 结论：稀疏 5+2 帧采样的“动作窗”多为单帧偶然/静止 → 全部窗口标注 `motion_support`（**WEAK 26 / MODERATE 2**）
- 诚实声明：当前动作识别证据强度低，**不宣称成熟**；改进方向 = 更高帧率（≥10fps 采样窗口内）+ 逐帧方向问题 + L3 人工锁定
- UI 本机操作补全：/api/trim(有界裁剪) + /api/replace 触发本地基础重QA(无qwen) 均冒烟通过；截图 reports/storage/ui_preview/workbench_main.png
"""
(DOCS / "TREECUT_STAGE8_G2_ACTION_SUBCLIP_REPORT.md").open("a", encoding="utf-8").write(upd_g2)
(OUT / "TREECUT_STAGE8_G2_ACTION_SUBCLIP_REPORT.md").open("a", encoding="utf-8").write(upd_g2)

steps = """# Workbench 操作步骤（晨间包 UI 段）
1. 启动：`runtime\\python.exe tools\\production_workbench\\server.py --port 8899`（已运行中）
2. 浏览器打开 http://127.0.0.1:8899/
3. 左侧点 Beat → 中部出现该 Beat 的 Claim 要求 + 播放区
4. 右侧候选卡：▶ 播放 = **subclip 窗口**（#t=start,end, 非整段）
5. 「替换本镜」→ 服务器持久化并跑本地基础重QA（无 qwen）；结果列表显示 PASS/WARNING/FAIL
6. 底部手动裁剪 start/end（有界）→「应用并重QA」
7. 关闭重开浏览器 → 状态保留（reports/storage/TREECUT_WORKBENCH_PROJECT_V1.json）
截图：reports/storage/ui_preview/workbench_main.png
"""
(OUT / "TREECUT_UI_STEPS_V1.md").write_text(steps, encoding="utf-8")
print("updated docs")
