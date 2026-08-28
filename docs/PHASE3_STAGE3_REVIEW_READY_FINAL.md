# PHASE3 STAGE3 — REVIEW READY FINAL（FINAL PRE-REVIEW SANITY CHECK）

> 状态：**PASS — 可以正式开始 Human Review（TARGETED_REVIEW_STAGE3_V3_1，60 条）**
> 日期：2026-08-28
> 范围：Calibration333 DEV ONLY；**Fresh Holdout V1 仅 READ-ONLY 访问**（特征提取/回归参考/泄漏审计；**未用于** training / calibration / threshold tuning / prompt tuning / routing tuning / model selection）
> 上承：PHASE3_STAGE3_FINAL_PRE_REVIEW_GATE.md（16 步收口）→ 本报告为 Sanity 收尾

---

## 1. People 混淆矩阵最终核验（PEOPLE_DETECTOR_BENCHMARK_V1.json 已修正）

**support：YES=237 · NO=93 · UNKNOWN=3（excluded）· n_valid=330**

**YOLOv8n conf=0.55（仅 Calibration333 选择，未用 Holdout truth）：**

| | 值 |
|---|---|
| TP | **237** |
| FP | **28** |
| TN | **65** |
| FN | **0** |
| sum 校验 | 237+28+65+0 = **330** ✓ |

**公式与指标（直接从混淆矩阵计算，未复制旧 aggregate）：**
- precision = TP/(TP+FP) = 237/265 = **89.4%**
- recall = TP/(TP+FN) = 237/237 = **100.0%**
- specificity = TN/(TN+FP) = 65/93 = **69.9%**
- f1 = 2PR/(P+R) = **94.4%**
- accuracy = (TP+TN)/(TP+FP+TN+FN) = 302/330 = **91.5%**
- balanced_accuracy = (recall+specificity)/2 = **84.9%**

**SigLIP 同真值：** TP=23 · FP=0 · TN=93 · FN=214 → P 100.0 / R 9.7 / Sp 100.0 / F1 17.7 / acc 35.2 / bacc 54.9

**旧数字勘误：** 旧版 `if pred_yes == t_yes: tp += 1` 把 **TN 计进 TP** → tp=302（=237+65），
导致旧 precision=302/330=91.5% 实为 accuracy；旧 F1=95.6% 也是同源高估。
**acc 91.5% 恰好正确**（分子同是 302），但 P/F1 必须按上表修正。预测本身未改动，只修 evaluation。

---

## 2. People threshold 确认

- conf=**0.55** 通过 CONF_GRID={0.15..0.55} 在 **Calibration333 上以 F1 选优**，无任何 Holdout truth 参与 → **保持 0.55**。

---

## 3. Calibration Near-Duplicate 最终处理（迭代替换）

旧 V3 中 2 条 NEAR_DUP_CALIBRATION 证据确凿（非审计误判）：
- `f30eb109…`（变体）↔ Cal `b321857d…`：cos 0.9986 + pHash(全帧最小) 2
- `4387fbec…`（人物）↔ Cal `e7c85fc7…`：cos 0.9992 + pHash 0（逐帧相同）

同时**旧 audit 因 pHash=None 漏检** 3 处更多违规（cal `2d328383…`、内部 pair `98d7c64f…/ed8256fb…` 等）。
本轮改为**全帧 pHash（帧间最小汉明）** 的迭代替换 audit：iter0 查出 EXACT=1/NEAR=7 → 替换 5 段（3 CAL + 2 内部端）→ iter1 **EXACT=0 / NEAR=0 达标**。

替换段（均 UNIQUE，保持 target）：
`f30eb109→71bc20d5(悬浮)` · `4387fbec→d780c9ed(师傅)` · `0ae2c9d2→4773064c(师傅)` ·
`2d328383→a678c4b5(抽屉/插座/伸缩)` · `ed8256fb→63e3616f(抽屉/柜门/插座)`

---

## 4. 替换后 Near-Dup 最终审计（TARGETED_REVIEW_STAGE3_V3_1.json）

阈值：EXACT = cos≥0.999；NEAR = cos≥0.99 或（cos≥0.95 且 pHash≤10）；UNCERTAIN = 0.93≤cos<0.95；Holdout 泄漏 = cos≥0.95（保守）。

| 对照集合 | EXACT | NEAR | UNCERTAIN |
|---|---|---|---|
| V3_1 vs Calibration333 | **0** | **0** | 26（灰区，允许记录） |
| V3_1 vs Fresh Holdout V1 | **0** | **0** | 0 |
| V3_1 internal | **0** | **0** | 16（灰区，允许记录） |

目标达成：**EXACT=0 · NEAR=0**（三集合）；UNCERTAIN 仅为灰区记录，不构成重复。

---

## 5. Manifest 重新冻结

- 新文件：**`TARGETED_REVIEW_STAGE3_V3_1.json`**（**未覆盖 V3**；V3 已标 `SUPERSEDED_BY_V3_1`）
- **manifest_sha256 = `f905d16bf61d03f20cca83cac3a7a355f41f3738a2f2e8dca6215d4d20c8ed02`**（sidecar `TARGETED_REVIEW_STAGE3_V3_1.sha256`）
- 总量 **60**（uniq segment 60 / uniq asset 60）；composition：SEMANTIC_ACTION 24 · PEOPLE 22 · PRODUCT_VARIANT 6 · SCENE 4 · MATERIAL 4；multi-target 46
- **Review Center 已指向 V3_1，启动状态 0/60（已程序确认表中无任何 V3_1 段）**

---

## 6. Fresh Holdout 表述修正（统一口径）

**正式表述：**
> Fresh Holdout V1 was READ-ONLY accessed for regression/reference/leakage audit only.
> It was NOT used for: training, calibration, threshold tuning, prompt tuning, routing tuning, model selection.

（本阶段对 Holdout 仅做了：423 段特征提取中的 30 段 read-only 推理、near-duplicate/leakage 审计、回归参考。未拿答案调阈值、未按错题改模型、未重预测替换原答案。）

---

## 7. 日期修正

本阶段实际日期：**2026-08-28**（已统一到本报告及 FINAL_PRE_REVIEW_GATE.md）。

---

## 8. 12 问答复

1. **YOLO TP/FP/TN/FN？** → TP=237, FP=28, TN=65, FN=0（sum=330 ✓）
2. **正确 P/R/F1/Accuracy？** → P 89.4% / R 100.0% / F1 94.4% / acc 91.5%（另 Sp 69.9%、bacc 84.9%）
3. **旧 91.5% accuracy 是否错误？** → **acc 91.5% 恰好正确**；错误的是旧 precision=91.5%（实为 accuracy）与旧 F1=95.6%，根因 TN 计入 TP，已修正
4. **People Detector 是否仍明显优于 SigLIP？** → **是**：YOLO F1 94.4 vs SigLIP 17.7；R 100 vs 9.7（同一 333 同真值）
5. **Calibration near dup 2 条最终如何处理？** → 证据确凿（cos 0.9986/0.9992 + pHash 2/0），已替换为 UNIQUE 候选（`71bc20d5`/`d780c9ed`）；另修复旧 audit 漏检的 3 处违规
6. **最终 60 条 vs Calibration 是否 NEAR=0？** → **是**（EXACT 0 / NEAR 0 / UNCERTAIN 26）
7. **最终 60 条 vs Holdout 是否 NEAR=0？** → **是**（EXACT 0 / NEAR 0 / UNCERTAIN 0）
8. **最终 60 条内部是否 NEAR=0？** → **是**（EXACT 0 / NEAR 0 / UNCERTAIN 16）
9. **最终 Manifest 文件名？** → `TARGETED_REVIEW_STAGE3_V3_1.json`
10. **完整 64 位 manifest SHA256？** → `f905d16bf61d03f20cca83cac3a7a355f41f3738a2f2e8dca6215d4d20c8ed02`
11. **Review Center 是否为 0/60？** → **是**（done=0，remaining=60，status=进行中）
12. **现在是否可以正式开始 Human Review？** → **可以**（GATE PASS；待用户放行后开启 `TARGETED_REVIEW_STAGE3_V3_1`）

---

## 附：本轮改动的文件

- `scripts/stage3_people_confusion_sanity.py`（混淆矩阵重建）
- `scripts/stage3_v31_replace.py`（迭代替换至 NEAR=0）
- `src/treecut/services/review_center.py`（TASKS 指向 V3_1）
- `tests/`（blind_ui / productization 指向 V3_1）
- `PEOPLE_DETECTOR_BENCHMARK_V1.json`（修正 P/R/Sp/F1/acc/bacc + TP/FP/TN/FN）
- `TARGETED_REVIEW_STAGE3_V3_1.json` + `.sha256`（冻结）；V3 标 SUPERSEDED_BY_V3_1

## 明确未做（按禁令）

- 未修改模型 / Policy / Prompt / Routing / Bundle；未 Phase4 / Fresh Holdout V2 / 全量 41814；未开始人工审核；未拿 Holdout 调参。
