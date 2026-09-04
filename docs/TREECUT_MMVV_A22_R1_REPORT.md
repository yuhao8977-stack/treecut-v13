# TreeCut MMVV A2.2 R1 — Camera Deterministic Closure 报告

> 阶段：MMVV A2.2 R1（架构师裁决 A2.2=PASS_WITH_DETERMINISTIC_CORRECTIONS；基线 main@36c393c）
> 修复范围：仅 SOCKET_01（1985/1986 unique case）相机链；不改 Geometry/Temporal 阈值、不加素材、无媒体/GT 硬编码。
> 原始证据：reports/storage/TREECUT_MMVV_A22_R1_CAMERA_DIAGNOSIS.json、TREECUT_MMVV_A22_R1_RESULTS.json

## 1. Warp 方向修复（R1 核心）
- 新增 canonical `warp_current_to_previous(curr, model, matrix)`：2x3/translation → `invertAffineTransform`；homography → `inv(H)`。scene_diff 一律用逆补偿把当前帧对齐回前一帧。
- **scene_diff 重算（背景掩码 + 逆补偿）**：
  | pair | OLD(A2.2 前向 warp) | NEW(R1 逆补偿) | 状态 |
  |---|---|---|---|
  | 1.9→2.525 | 0.741 | **0.606** | SAME_SCENE |
  | 2.525→3.15 | 0.574 | **0.439** | SAME_SCENE |
  | 3.15→3.775 | 0.814 | **0.795** | SAME_SCENE |
  | 3.775→4.4 | 0.902 | **0.836** | SAME_SCENE |
  旧值标记 `INVALIDATED_BY_WARP_DIRECTION_BUG`（保留未覆盖）。修正后差异整体更低（逆补偿语义正确）。

## 2. 双模式差分诊断（根因机器派生，无硬编码）
同一 pair 跑 `MODE_FULL_FRAME` 与 `MODE_BACKGROUND_MASKED`：
| pair | full_frame | background_masked | 机器根因 |
|---|---|---|---|
| 1.9→2.525 | CAMERA_MODEL_UNRELIABLE | SAME_SCENE, resid 1.137 | FOREGROUND_CONTAMINATED |
| 2.525→3.15 | CAMERA_MODEL_UNRELIABLE | SAME_SCENE, resid 0.919 | FOREGROUND_CONTAMINATED |
| 3.15→3.775 | CAMERA_MODEL_UNRELIABLE | SAME_SCENE, resid 1.341 | FOREGROUND_CONTAMINATED |
| 3.775→4.4 | SAME_SCENE, resid 2.548 | SAME_SCENE, resid 2.020 | NONE_CAMERA_OK |

判定规则（机器证据，非 media/pair/GT）：FULL_FRAME_UNRELIABLE + BACKGROUND_MASKED_RELIABLE + SAME_SCENE → FOREGROUND_CONTAMINATED。删除了 runner 里手填 root_cause 与手填 baseline 25.353（full_frame 残差现在由程序实测）。

## 3. 修复相机回喂目标运动（不再手填 0）
- 用背景掩码选定模型（translation）做**逆补偿**后，在真实 TABLETOP ROI 实测：
  - target_pixel_motion_before_compensation = **0.7166**
  - target_pixel_motion_after_compensation = **0.7217**
- 诚实说明：after≈before（背景相机运动很小，桌板 ROI 差异非运动主导；补偿后差异未显著下降——这是真实数字，不是手填）。该指标不改变判定（几何 STATIC 优先 → FAIL）。

## 4. Holdout 术语诚实
字段更名 `heldout_background_residual_px` → `background_validation_residual_px`，并注明"全背景 track 拟合后残差（非独立 70/30 holdout）"。

## 5. 最终 SOCKET_01 裁决
链：BackgroundCameraEstimate(全部 SAME_SCENE) → 逆补偿 → 真实 target motion → GeometryDirectionEvidence(STATIC_WITH_ANNOTATION_JITTER) → Validator
→ **机器 FAIL EXTEND**（相机 RELIABLE + 几何静止 + 无 EXTEND progression；非强制）。camera_state=RELIABLE（4/4 SAME_SCENE）。

## 6. Core5 真重跑（子进程运行当前 mmv_a21_run.py，非读历史）
| slice | stored-old(A2.1b) | actual rerun(R1) |
|---|---|---|
| 52_DRAWER_OPEN | PASS | **PASS** |
| 109_ACTION_POSITIVE | PASS | **PASS** |
| 109_OPEN_STATE_NEGATIVE | FAIL | **FAIL** |
| 89_EXTEND | FAIL | **FAIL** |
| 51_EXTEND | FAIL | **FAIL** |
False PASS = 0 → **core5 ok = True**（真重跑 5/5，非仅历史文件）。

## 7. Duplicate 治理（保持）
1985/1986 = 1 unique visual case（frame_hash_equivalent=true, unique=1, source_ref=2）。

## 8. 测试
tests/test_mmvv_a22.py 现含**真实独立前景合成**（背景 (+2,-1) + blob 额外 (+10,+6)，非整帧二次 warp）与 **warp 方向测试**（逆补偿 diff < 前向 diff）等 10 项；+A2.1b(9)+A2.1(9) = 28 passed。

## 9. 状态
**A2_2_R1_CAMERA_CLOSURE_PASS**（≠ CAMERA_SYSTEM_PASS ≠ MMVV PRODUCTION READY）。成功条件全满足：inverse 补偿正确 ✓、scene diff 重算 ✓、根因机器派生 ✓、synthetic 前景测试真实 ✓、target motion 真实重算且不手填0 ✓、Core5 真重跑 5/5 ✓、SOCKET_01 verdict 证据闭环 ✓、False PASS=0 ✓。

## 10. 下一步（等架构师）
按你的路线：**真实伸缩桌板 EXTEND 正例 → 未参与规则设计的新样本泛化验证**。禁止：改几何/时序阈值、新VLM、Qwen、重框、加新素材前的 Camera 继续折腾、Pilot V3、Blind30-50、Stage9、Orchestrator。
