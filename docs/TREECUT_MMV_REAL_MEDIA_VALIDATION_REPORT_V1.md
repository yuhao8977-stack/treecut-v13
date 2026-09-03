# MMV Real-Media Validation V1（2026-09-03 15:40:17）— MODE=SHADOW

| media | 请求 | Verdict | 人工预期 | 说明 |
| --- | --- | --- | --- | --- |
| 89 | Action.EXTEND | Verdict.FAIL | EXTEND FAIL | {"target_object_visible": "PASS", "target_object_motion": "FAIL", "opposite_absent": "PASS"} |
| 52 | Action.DRAWER_OPEN | Verdict.UNSURE | DRAWER_OPEN PASS/STRONG_UNSURE | {"target_object_visible": "PASS", "target_object_motion": "PASS", "opposite_absent": "PASS", "direction": "UNSURE", "state_transition": "UNSURE"} |
| 109 | Action.DRAWER_OPEN | Verdict.FAIL | OPEN_STATE TRUE / ACTION FAIL | {"target_object_visible": "PASS", "target_object_motion": "FAIL", "opposite_absent": "PASS"} |
| 51 | Action.EXTEND | Verdict.UNSURE | STATIC; EXTEND FAIL | {"target_object_visible": "PASS", "target_object_motion": "PASS", "opposite_absent": "PASS", "direction": "UNSURE", "state_transition": "UNSURE"} |
| 1985 | Action.EXTEND | Verdict.UNSURE | SOCKET_ADJUST; EXTEND FAIL | {"target_object_visible": "PASS", "target_object_motion": "PASS", "opposite_absent": "PASS", "direction": "UNSURE", "state_transition": "UNSURE"} |
| 1986 | Action.EXTEND | Verdict.UNSURE | SOCKET_ADJUST; EXTEND FAIL | {"target_object_visible": "PASS", "target_object_motion": "PASS", "opposite_absent": "PASS", "direction": "UNSURE", "state_transition": "UNSURE"} |

## 结论
- **无假 PASS**；89 人动桌板不动 → EXTEND FAIL ✓；109 开着≠打开 → DRAWER_OPEN FAIL ✓；52 抽屉运动 → UNSURE(PASS/STRONG_UNSURE 区间内) ✓
- 51/1985/1986 = UNSURE(方向/状态未证, 保守): 1985/86 暴露启发式 ROI 局限(插座运动进入下层 TABLETOP ROI 抬升 motion, 但 direction gate 拦截 PASS) — 与预期 FAIL 的差异如实记入 DISAGREEMENTS, 需要 object-specific analyzer 精修
- Shadow Mode: 仅输出判断, 未改 Production 选择; Enforcement 需人工批准
- 局限: qwen 未返回 bbox → ROI=HEURISTIC; camera 平移级(未做 affine 第二级); 阈值 PROVISIONAL
