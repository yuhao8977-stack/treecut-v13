# Multi-label Overprediction Audit V1（Stage 3 STEP 1）

- **日期**：2026-08-28 18:44 ｜ 数据：Calibration333 + Fresh Holdout30（AI final routed prediction vs Human truth）
- **结论（铁证）**：**存在系统性过预测（撒网）**——AI 平均输出 5-8 个标签，人工 1-3 个。

## 1. 标签数统计

| 字段 | 人工 avg(ho) | 预测 avg(ho) | delta | 预测 1 标签% | 预测 4+ 标签% | 判定 |
|---|---|---|---|---|---|---|
| material | 0.97 | 4.63 | 3.66 | 0.0% | 90.0% | **OVERPREDICTION** |
| component | 2.5 | 5.63 | 3.13 | 0.0% | 100.0% | **OVERPREDICTION** |
| function | 3.23 | 7.83 | 4.6 | 0.0% | 100.0% | **OVERPREDICTION** |
| shot_role | 2.13 | 7.33 | 5.2 | 0.0% | 100.0% | **OVERPREDICTION** |

| 字段 | 人工 avg(cal) | 预测 avg(cal) |
|---|---|---|
| material | 1.0 | 4.86 |
| component | 1.06 | 5.33 |
| function | 1.46 | 8.17 |
| shot_role | 0.66 | 7.1 |

## 2. 解读

- Holdout：material 预测 4.63 vs 人工 0.97；function 预测 7.83 vs 人工 3.23；shot_role 预测 7.33 vs 人工 2.13
- **预测 1 标签比例 = 0%**（全部输出 ≥3 标签），4+ 标签 90-100% → **label-in 90-97% 的"高命中"是撒网假象**，precision 被稀释（microF1 仅 23-56%）
- 之前 `_classify_multi_emb` 的 `s >= top1 - 0.06` 阈值过宽 → 几乎全选

## 3. 处置（CANDIDATE，STEP 2）

- **Multi-label Decision Policy V2**（已实现于 `static_vision_v2.MULTI_POLICY`）：per-field Top-K（material 2 / component 3 / function 3 / shot_role 3）+ score gap 0.10 + min score
- 阈值**只能在 Calibration333 调整**（禁止用 Holdout V1）；本审计已确认问题，Policy V2 的 333 验证在 Stage3 下一轮执行
- 预期：压缩预测集 → label-in 略降但 precision/microF1 显著升
