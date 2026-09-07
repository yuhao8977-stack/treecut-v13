# POST-A3 CAM01 V2.2 — Local Anchor Validity Closure + Target Relative Bug Fix 报告

- 日期：2026-09-07 · main @ d818158 → 本次提交
- 未改阈值/ROI/GT；不读 A3；不造叶板页；不融合

## 第一屏（§19）
| 项 | 值 |
|---|---|
| target bbox bug fixed | **YES**（t0/t1 分别取 target；EXTENSION_TABLETOP 优先→TABLETOP fallback→INSUFFICIENT；不再复用 t1 框算 f0） |
| local validation leakage fixed | **YES**（deterministic 网格 2-fold：fit fold ≠ validate fold；拟合内残差不再当独立验证） |
| total semantic pairs | 40 |
| island present pairs | 36（2212 无岛台 → 4 对不适用） |
| holdout validated pairs | **14**（LOCAL_ANCHOR_VALIDATED） |
| anchor 状态分布 | VALIDATED 14 · NOT_VALIDATED 8 · PARTIAL 2 · INSUFFICIENT 12 · N/A 4 |
| local anchor reliable % | 14/40 = **35.0%**（以独立 holdout 计；V2.1 "29/29 亚像素" 为拟合内残差，已证实偏乐观） |
| holdout median residual | 仅 VALIDATED 对上 3.0px 门内（两折 median ≤3.0 才计）；原始分布见 JSON |
| holdout P90 / worst fold | 见 JSON（每对两折 median/p90 已录） |
| POS3 anchor-comp target signal | 存在（9 个 VALIDATED 对：span_w_d −0.70…+0.28、cx_d ±0.4、像素 after 0.19–1.02），但**符号/幅度不一致**（非单一单调推进） |
| NEG anchor-comp target signal | 仅 1 个有效对（2543：span 0.038 / px after 0.335）→ **n=1，无法作统计对照** |
| separation 是否存在 | **未确立**（POS 亦有小增量、NEG 仅 1 例；须更多 validated 负例或锚点补偿像素判别进一步验证） |
| leaf ROI decision | **LEAF_ROI_DEFERRED_ANCHOR_NOT_VALIDATED**（独立验证覆盖率仅 35%，先不画叶板） |
| CAM01 V2.2 status | **CAM01_V22_PARTIAL**（local anchor = LOCAL_ANCHOR_PARTIAL） |

## 关键结论
1. **Local Island Anchor 从"promising"降级为 PARTIAL**：独立 holdout 下仅 35% 对 VALIDATED（岛台纹理不足/匹配不稳时 INSUFFICIENT 12、NOT_VALIDATED 8）。
2. **修正 t0/t1 配对后**，POS3 在 VALIDATED 对确有锚点补偿相对运动（非零信号），但幅度/方向在相邻对间振荡（可能含相机推拉残留、岛台框变化、叶板局部遮挡），且负例有效样本 n=1 → **不能据此判定"粗 ROI 够用"或"需叶板"**。
3. 全局 Camera（40%）与 Local Anchor（35% VALIDATED）在本素材都只 PARTIAL；两者互补但都不足以作为强制前置闸 → 支持未来"LOCAL_ANCHOR→GLOBAL→UNSURE"证据层级方向（本轮不融合）。

## 历史解释（不覆盖 V2.1）
- V2.1 有效结论：global camera ≈40% partial；提出 local anchor 假设；其 0.78px 残差为拟合内、目标相对运动存在 t1 复用 bug（本 audit 明确记录 TARGET_RELATIVE_T1_BBOX_REUSED_FOR_T0=TRUE、LOCAL_ANCHOR_RESIDUAL_IN_SAMPLE=TRUE）。
- V2.2 收口：独立验证后 anchor=PARTIAL；修正后目标相对信号存在但分离未确立。

## 产物
reports/storage/TREECUT_CAM01_V22_METHOD_AUDIT.json · _LOCAL_ANCHOR_VALIDATION.json ·
_TARGET_RELATIVE_GEOMETRY.json · _TARGET_PIXEL_EDGE_MOTION.json · scripts/posta3_cam01_v22.py
