# MMV Real-Media Hardening R2 — Semantic ROI + Target Motion（2026-09-03 18:04:38）

状态: **MMVV_R2_KNOWN_CASE_NEEDS_REPAIR**（无假 PASS；3/6 未达预期）

| media | 请求 | Verdict | 预期 | 达标 |
| --- | --- | --- | --- | --- |
| 89 | Action.EXTEND | Verdict.UNSURE | FAIL | ❌ |
| 52 | Action.DRAWER_OPEN | Verdict.UNSURE | PASS/STRONG_UNSURE | ✅ |
| 109 | Action.DRAWER_OPEN | Verdict.UNSURE | FAIL | ❌ |
| 51 | Action.EXTEND | Verdict.UNSURE | FAIL | ❌ |
| 1985 | Action.EXTEND | Verdict.UNSURE | FAIL | ❌ |
| 1986 | Action.EXTEND | Verdict.UNSURE | FAIL | ❌ |

## 阻塞(非阈值问题, 未调阈值)
1. **Semantic ROI 获取不可行(当前)**: qwen2.5vl 对"多对象 bbox JSON"任务回显允许名联合/绝对像素坐标/伪 JSON(已存原样证据) → MODEL_DETECTED ROI 无法获得
2. **机械归属不足**: 布局启发式 person 带(顶部)+小簇排除 仍让残差/人带重叠抬升目标核心运动 → 51/1985/1986 仍 UNSURE 而非 FAIL(方向门保守, 无假 PASS)
3. 相机 translation+部分 affine 补偿不够干净(残差高)

## 建议(等架构师拍板, 未执行)
- 允许 **HUMAN 首帧 ROI**(6 案例人工框选, roi_source=HUMAN) 作为校准基线 → 再验归属/门序
- 或引入轻量检测器(受模型禁令约束, 需批准)
- 之后重跑 Known6 → 达标才 Blind30-50(仍 Shadow)
