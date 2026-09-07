# POST-A3 CAM01 V2.6 — Pair-Level Clean Support Region 报告（FAIL）

- 日期：2026-09-07 · main @ d2ec9b7 → 本次提交
- 未调阈值/不读 A3/无新人工/region 选择不用动作 GT；6×6 canonical、min_clean_px=800、corners≥12、真 clique≤3px 均跑前冻结

## 0. V2.5 修正（corrections json）
- `CAM01_V25_DEFECT_OVERLAP_SUM_01`：overlap 由"多框交叉面积累加"改**真 union raster ∈[0,1]**（回归测试 2 项过：完全重叠两框不得>1；分离框 0.32）。
- V2.5 no-data `true_pooled=0.0` → 应为 null；island-present cases = **9**（非 8）。V2.5 历史 0/36 不改写。

## 1. 主结果（36 island-present pairs）
| 指标 | 值 |
|---|---|
| pair common-clean availability | **34/36**（架构师 pair 级预判命中：V2.5 把干净区全丢是因为"5 帧永久"规则） |
| avg candidate regions/pair | 4.94（top6 内） |
| validated region instances | 31 |
| PAIR_REGION_MULTI /36 | **2** |
| PAIR_REGION_SINGLE /36 | 5 |
| PAIR_REGION_CONFLICT /36 | 6 |
| PAIR_REGION_NO_ANCHOR /36 | 23 |
| region union /36 | **7** |
| case coverage /9 | 3（multi case 1/9） |
| true pooled median / P90 / P95 | **0.436 / 1.774 / 3.317 px**（验证成功处质量极佳） |

## 2. 基线对比（不变）
V24R1 consensus 12/36 · GFTT whole-island 17/36 · V25 case-patch 0/36 · **V26 pair-region multi 2 · union 7**。

## 3. 困难案例
1641：4 对 NO_ANCHOR（候选 3–5，均未过严格验证）；10000：1 CONFLICT + 3 NO；2543：0–4 候选、4 对 NO（两对 <2 候选）；
21674：0–6 候选、4 对 NO。无 media-id 特判。

## 4. NEG target control（严格 t0/t1 contract）
- MULTI consensus：0 case/pair；SINGLE：0 case/pair（V2.6 少数 validated 均集中在 POS/25894；不设 EXTEND threshold）。

## 5. 判定（§19 预置）
- union 7 < 20 → **improvement class = FAIL**；按 §22 正式停止 grid/detector/mask/patch 路线。
- **NEXT_BLOCKER = STRUCTURAL_OBJECT_ANCHOR_V1**（固定柜体轮廓/长边/角点/侧板/框架线的对象级结构参照；不做 V2.7 继续磨 grid）。
- 保留观察：pair-level "clean support 可用性" 确实远好于 V2.5（34/36 vs 0），且**验证成功处残差亚像素级（0.44/1.77）**——证明"岛台局部参照"机制本身成立，瓶颈在 6×6 网格 cell 内可提特征太少（清理后每区 GFTT 常 <12 或过不了 2-fold），需要对象级/结构级更大且稳定的特征面。

## 产物
reports/storage/TREECUT_CAM01_V26_CONFIG.json · _V25_CORRECTIONS.json · _PAIR_CLEAN_SUPPORT.json ·
_REGION_METHOD_MATRIX.json · _REGION_CONSENSUS.json · _NEG_TARGET_CONTROL.json · _RESULT.json ·
TREECUT_CAM01_V26_PAIR_REGION_GALLERY.html · scripts/posta3_cam01_v26.py ·
tests/test_cam01_v25_overlap_union.py
