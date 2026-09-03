# STAGE8 Candidate Discovery Recovery V1 报告（2026-09-03 14:05:41）

## 结论
- Recall 验证(分层漏斗, 非 Top3): Eligible 池每动作宽召回数百(EXTEND 327/DRAWER 395/STORAGE 396/SOCKET 394), 样本(10/动作)+qwen(4/动作) 后 **0 通过动作门**(方向 UNCERTAIN/静态 保守拒绝) → Eligible 池标签下动作证据稀缺
- **不得标 MATERIAL_GAP_CONFIRMED**：REVIEW_REQUIRED 高价值候选(EXTEND 21/DRAWER 59/STORAGE 60/SOCKET 17=157) 未做 contamination verify；跨段合并结构候选 13,605 未做时序探测；样本非穷举
- 不要求补拍；下一步 = 定向 verify REVIEW_REQUIRED 高价值 + 跨段候选时序探测(有界 qwen)

## 每动作漏斗
| Action | Broad | Sample | Motion短名单 | Qwen | TVRC PASS | TVRC FAIL |
| --- | --- | --- | --- | --- | --- | --- |
| EXTEND | 327 | 10 | 4 | 4 | 0 | 2 |
| RETRACT | 327 | 10 | 4 | 4 | 0 | 0 |
| DRAWER_OPEN | 395 | 10 | 4 | 4 | 0 | 2 |
| STORAGE_PUT_IN | 396 | 10 | 4 | 4 | 0 | 2 |
| SOCKET_INSERT | 394 | 10 | 4 | 4 | 0 | 0 |

## 输出
- TREECUT_ACTION_CANDIDATE_DISCOVERY_V1.json / TREECUT_{EXTEND,RETRACT,DRAWER_OPEN,STORAGE_PUT_IN,SOCKET_INSERT}_DISCOVERY_V1.json
- TREECUT_REVIEW_REQUIRED_ACTION_RECOVERY_V1.json（未提升 G1；promotable=False 待 verify）
- TREECUT_CROSS_SEGMENT_ACTION_RECOVERY_V1.json（13,605 结构候选；不重写 canonical）
- TREECUT_MATERIAL_GAP_STATUS_V2.json（CANDIDATE，非 CONFIRMED）
- 新有效候选 0 → 未生成新动态审核包（无可播新画面）；REVIEW_REQUIRED/跨段验证出候选后再重建
