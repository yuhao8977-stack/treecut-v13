# STAGE8 Candidate Discovery Recovery V1.1 报告（2026-09-03 14:48:27）

## 结论
- **不再随机10**：五动作 Eligible 池全量廉价排序(flexible 333 共享 EXTEND/RETRACT, drawer 888, storage 1200, socket 464) → 运动代理 top24 → 短名单12 → qwen top6 → **TVRC 0 PASS**
- REVIEW_REQUIRED 定向验证并**正规 G1 提升 57 条**（EXTEND12/RETRACT9/DRAWER12/STORAGE12/SOCKET12，记录 recovery_v11 证据）——但其顶候选动作验证仍未通过（NO_ACTION/UNCERTAIN）
- **跨段边界恢复有发现**：13,605→动作相关40→31 连续 → 合并窗动作态 PASS 4 条（media 51/109/89/52，flexible 族）——方向复核多为 STATIC/UNCERTAIN、media89=EXTEND(L2) → **UNSURE 待人工**
- 结论：Recall 在三支线均深挖后，Eligible/RR 仍无确认动作；跨段合并证明"切镜切断动作"真实存在并恢复出运动候选 → **不得 CONFIRMED**，先人工看 4 条合并窗

## 漏斗指标（§23）
| Action | 全量廉价 | 运动探测 | 短名单 | Qwen | TVRC PASS | RR提升 | 跨段合并motion |
| EXTEND | 60 | 17 | 12 | 6 | 0 | 12 | 4 |
| RETRACT | 60 | 17 | 12 | 6 | 0 | 9 | 4 |
| DRAWER_OPEN | 60 | 24 | 12 | 6 | 0 | 12 | 4 |
| STORAGE_PUT_IN | 60 | 24 | 12 | 6 | 0 | 12 | 4 |
| SOCKET_INSERT | 60 | 24 | 12 | 6 | 0 | 12 | 4 |

## 新候选(人工)
- TREECUT_G2_CROSSSEG_REVIEW_V1.mp4/.json：4 条合并窗(含 contexts)，方向/对象待人工
