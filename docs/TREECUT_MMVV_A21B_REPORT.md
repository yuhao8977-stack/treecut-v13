# TreeCut MMVV A2.1b — Robust Static Geometry / Jitter Separation 报告

> 阶段：MMVV A2.1b（架构师批准 2026-09-04；基线 main@eef5b9a）
> 冻结：200 L3_HUMAN_ROI / 32 帧 / 7 slices / 现有绑定 / Human GT（未重框、未改绑定、未加帧）
> 原始证据：reports/storage/TREECUT_MMVV_A21B_RESULTS_V1.json（每 slice 含 raw 几何序列 / robust 统计 / MAD / reversal / monotonicity / camera reliability / geometry state / pixel motion / verdict / GT / match）

## 1. 结果总览（机器 vs 人工）
| slice | 机器 | GT | 一致 | 几何状态 | 相机 | 判定代码 |
| --- | --- | --- | --- | --- | --- | --- |
| 52_DRAWER_OPEN | **PASS** | PASS | ✅ | PROGRESSION_UP | RELIABLE | GEOMETRY_PROGRESSION_SUPPORTED |
| 109_ACTION_POSITIVE | **PASS** | PASS | ✅ | PROGRESSION_UP | RELIABLE | GEOMETRY_PROGRESSION_SUPPORTED |
| 109_OPEN_STATE_NEGATIVE | **FAIL** | FAIL | ✅ | STATIC_WITH_ANNOTATION_JITTER | RELIABLE | NO_GEOMETRY_PROGRESSION + OPEN_STATE_NOT_OPEN_ACTION |
| 89_EXTEND | **FAIL** | FAIL | ✅ | STATIC_STABLE | RELIABLE | NO_TARGET_GEOMETRY_CHANGE |
| 51_EXTEND | **FAIL** | FAIL | ✅ | STATIC_WITH_ANNOTATION_JITTER | RELIABLE | NO_TARGET_GEOMETRY_CHANGE |
| 1985_EXTEND | UNSURE | FAIL | ⚠️允许 | STATIC_WITH_ANNOTATION_JITTER | **UNRELIABLE(真实证据)** | CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE |
| 1986_EXTEND | UNSURE | FAIL | ⚠️允许 | STATIC_WITH_ANNOTATION_JITTER | **UNRELIABLE(真实证据)** | CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE |

- **一致 5/7（核心 5 = 5/5）**；False PASS 0；False FAIL 0；UNSURE 2（1985/86，规格允许）。
- **正例保护**：52 与 109_ACTION_POSITIVE 保持 PASS（未退化）。
- **成功门（§13）达标**：核心5 ≥4/5（5/5）∧ False PASS=0 ∧ 52/109前 PASS 保持 → **ROBUST_GEOMETRY_CHANNEL = PARTIAL_PASS_APPROVED_FOR_NEXT_STAGE**（5/5 仍不等于 Production Ready）。

## 2. 关键修复落实
1. **删除样本硬编码**：runner 不再有 `cam_unrel = mid in (1985,1986)`。相机可靠性由 `CameraReliabilityEvidence`（逐对 `compensate_pair` 的 reliable/inlier_ratio/feature_residual/translation_px）自动形成——1985/1986 因真实逐对 residual≈25 / reliable=False 自动判 **UNRELIABLE**（与样本号无关）。
2. **鲁棒静态判定（JITTER 分离）**：新增中位归一化统计（median_area / MAD_ratio / first_last_change / reversal_count / monotonicity_score / pair_max_frac / center_drift / net_geometry_change / direction_consistency）。判定规则（provisional，未为 GT 调参）：
   - 单调一致 + 净增长 ≥10%（或 factor≥1.15）→ PROGRESSION_UP/DOWN；
   - 有界振荡（|净变化|≤10% 且 MAD/中位 ≤12%）→ **STATIC_STABLE（pair≤6%）或 STATIC_WITH_ANNOTATION_JITTER（pair 局部 >6% 也接受）**——非单调不再自动 = UNKNOWN；
   - 否则 UNKNOWN。
   `_GEOM_STATIC_TOL=0.06` 保留，仅作"局部 pair 参考"，不再是唯一判据。

## 3. 109后段与 51 诊断（§17）
- 109 后段：面积 41,302→37,541→43,665，reversal≥2、首尾净变化≈5.7%、MAD≈6% → **STATIC_WITH_ANNOTATION_JITTER** → FAIL（OPEN_STATE_NOT_OPEN_ACTION）✅。
- 51：面积围绕 ~410k 振荡（±3–5%），净变化≈2% → **JITTER** → FAIL（NO_TARGET_GEOMETRY_CHANGE）✅。
- 52/109前段：单调净增长 79%/150% → PROGRESSION_UP，未被静态鲁棒性压坏 ✅。

## 4. 1985/1986 状态
几何已判 STATIC（JITTER），但真实 Camera 证据 UNRELIABLE → 按规格保持 **UNSURE(CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE)**，不强制 FAIL、不绕过相机门。→ 适合进入 A2.2（仅相机）。

## 5. 边界（不变）
- 无真实 EXTEND 正例 → 89/51 的 FAIL 只证明 NON_EXTEND REJECTION，**不得宣称 EXTEND 正识别 PASS**。

## 6. 测试
新增 `tests/test_mmvv_a21b.py`（9 项）全通过：small_nonmonotonic_jitter_is_static / large_monotonic_growth_is_action / positive_drawer_regression_preserved / alternating_bbox_noise_not_progression / net_change_small_but_pair_noise_large_is_static / camera_reliability_not_media_id_hardcoded / camera_unreliable_can_stay_unsure / same_classifier_all_media / no_gt_used_in_machine_features；回归 a21(9)+mmvl_r2(6+4xfail) 全绿。

## 7. 结论与下一步
A2.1b 达成架构师设定的成功门：核心 5/5 一致、0 假 PASS、正例保持 PASS、相机来源真实化。**GEOMETRY/TEMPORAL CORE（当前抽屉+静态集）= PASS_FOR_CURRENT_SET（按 §八 判定口径）**。下一步仅限（等批准，不自动执行）：**A2.2（只解决 1985/1986 相机）**；其后必须补**真实伸缩桌板 EXTEND 正例**。禁止：Pilot V3 / Blind30-50 / Stage9 / 新 VLM / Qwen / 加帧 / 重框。
