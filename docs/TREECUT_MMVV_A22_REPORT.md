# TreeCut MMVV A2.2 — Camera Failure Diagnosis + Minimal Repair 报告

> 阶段：MMVV A2.2（架构师批准 2026-09-04；基线 main@3b7af85）
> 对象：唯一相机 hard case **CAMERA_CASE_FAMILY_SOCKET_01**（media1985/1986 冻结窗口帧 sha256 逐张相同 → unique visual case = 1，source ref = 2）
> 产物：reports/storage/TREECUT_MMVV_A22_CAMERA_DIAGNOSIS_V1.json（4 pair 全诊断原始数据）、TREECUT_MMVV_A22_RESULTS_V1.json、docs/TREECUT_MMVV_A22_REPORT.md

## 0. Duplicate 治理（§0/§13）
1985 与 1986 在冻结窗口 [1.9,2.525,3.15,3.775,4.4] 的 5 张采样帧 sha256 逐张相同 → **unique_visual_case_count = 1**（不得写成 2/2；统计口径 = 1/1 或 0/1）。

## 1. 4 pair 诊断（背景掩码 LK + 前向-反向 + 模型阶梯；真实机器证据）
| pair | 背景掩码状态 | 选定模型 | 留出背景残差(px) | scene_diff | 根因 |
| --- | --- | --- | --- | --- | --- |
| 1.9→2.525 | SAME_SCENE | translation | 1.137 | 0.741 | 背景稳定 |
| 2.525→3.15 | SAME_SCENE | translation | 0.919 | 0.574 | 背景稳定 |
| **3.15→3.775** | **SAME_SCENE** | translation | **1.341** | 0.814 | **前景污染（非跳变、非模型不足）** |
| 3.775→4.4 | SAME_SCENE | translation | 2.020 | 0.902 | 背景稳定 |

**pair3 根因结论**：全帧估计 residual 25.353 的来源是 **FOREGROUND_CONTAMINATED**——手/插座模块/目标桌板等前景运动主导全帧特征点；一旦用 L3 ROI 掩码把前景排除、只用稳定背景角点，4 个 pair（含 pair3）全部 SAME_SCENE、最简模型=translation、残差 0.9–2.0px。**不存在 SCENE_DISCONTINUITY（无需拆段/不强行 warp），也无需 homography/稠密光流。**
（注：背景掩码 LK 为本受控实验方法，明确不是 production 必需条件。）

## 2. 修复后相机证据与最终唯一 case verdict
- 相机：4/4 pair SAME_SCENE、model=translation、**camera_state = RELIABLE**（来自真实逐对证据；无 media_id 特例、未放宽可靠性门槛——门槛反而来自背景留出残差评估）。
- 目标几何（沿用 A2.1 绑定）：STATIC_WITH_ANNOTATION_JITTER；相机不再阻塞 → validator 几何优先 → **FAIL EXTEND（NO_TARGET_GEOMETRY_CHANGE）**，由机器证据产生。
- **唯一 case 最终状态：A2_2_CAMERA_CASE_PASS**（1 unique case；**≠ CAMERA_SYSTEM_PASS**）。
- Core5 冻结回归：52/109前段 PASS、109后段/89/51 FAIL —— **5/5 保持，0 假 PASS**（读取 A2.1b 结果核验）。

## 3. 测试
新增 tests/test_mmvv_a22.py（9 项）全部通过：foreground_tracks_excluded / forward_backward_bad_tracks_rejected / scene_discontinuity_not_force_warped / simplest_reliable_model_selected / camera_model_not_media_id_specific / duplicate_media_not_counted_twice / unreliable_camera_can_remain_unsure / core5_results_frozen / no_gt_in_camera_selection（+A2.1b 9 项回归，18 passed）。

## 4. 边界与下一步
- 本次只修好 **1 个 unique camera case**；不能宣称"Camera Robustness 已验证"。
- 下一步（等架构师批准，不自动执行）：**补真实伸缩桌板 EXTEND 正例 → 用未参与规则设计的新样本验证泛化**。
- 禁止：改几何/时序阈值、新 VLM、Qwen、重框、Pilot V3、Blind30-50、Stage9、Orchestrator。
