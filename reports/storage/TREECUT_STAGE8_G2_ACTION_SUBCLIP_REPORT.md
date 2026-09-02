
## 更新（2026-09-02 20:01）— 方向复核与证据强度

- 对已检出动作窗的 6 素材在动作时刻做 EXTEND-vs-RETRACT 独立复核：2482/2483/2484/1984 → **STATIC**，1985/1986 → EXTEND
- 结论：稀疏 5+2 帧采样的“动作窗”多为单帧偶然/静止 → 全部窗口标注 `motion_support`（**WEAK 26 / MODERATE 2**）
- 诚实声明：当前动作识别证据强度低，**不宣称成熟**；改进方向 = 更高帧率（≥10fps 采样窗口内）+ 逐帧方向问题 + L3 人工锁定
- UI 本机操作补全：/api/trim(有界裁剪) + /api/replace 触发本地基础重QA(无qwen) 均冒烟通过；截图 reports/storage/ui_preview/workbench_main.png
