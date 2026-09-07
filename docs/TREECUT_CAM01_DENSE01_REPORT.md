# POST-A3 CAM01 DENSE01 — DINOv2 Dense Semantic Correspondence 报告（FAIL_DENSE）

- 日期：2026-09-07 · main @ 1d470ab → 本次提交
- 模型：dinov2_vits14_reg（facebookresearch/dinov2 hub，**Apache-2.0**；权重 sha256 见 MODEL_PROVENANCE.json，G 盘缓存）
- CUDA 运行；不读 A3；不用动作 GT；无特判

## 0. 环境
- device=cuda（runtime torch 2.6.0+cu124）；模型加载 18s；smoke tokens [1,1369,384] 通过。
- 缓存：G:\TreeCut_AI\torch_cache（未写 C/Desktop/Downloads）。许可证记录 Apache-2.0。

## 1. 主结果（36 pairs）
| 指标 | 值 |
|---|---|
| DINO match sufficient /36 | **36/36**（MNN 处处可用，210–270 级对应） |
| pixel(subtoken) refine | 已应用（soft 3×3） |
| PARTIAL_AFFINE validated /36 | 0 |
| HOMOGRAPHY validated /36 | 0 |
| DENSE_MULTI /36 | 0 |
| DENSE_SINGLE /36 | 0 |
| DENSE_CONFLICT /36 | 0 |
| DENSE_NO_ANCHOR /36 | 36 |
| dense union /36 | **0** |
| case coverage /9 | 0 |
| pooled holdout median/P90/P95 | null（无 validated） |

- fold 画像（代表 27433）：fit inlier 0.46–0.78（拟合稳健）；**holdout median 4.3–13.4px，P90 20–33px** —— DINO 端点语义对应在 1–4s 大位移语义帧对上精度约 5–8px 级，达不到 3px（median）与 8px（P90）门；尾重来自非刚体/透视/取景变化。

## 2. 困难案例
1641/10000/2543/21674：MNN 均足够但模型验证未过（同上残差画像）。无特判。

## 3. NEG target control
MULTI 0 · SINGLE 0（真实 contract；无 validated anchor）。

## 4. 判定（预置门槛）
- **FAIL_DENSE**（union 0 < 17）→ **DENSE_SEMANTIC_ENDPOINT_CORRESPONDENCE_NOT_ESTABLISHED = YES**。
- 按 §31：不换 DINO-B/L、不改 similarity/threshold/更多 RANSAC；STOP。
- NEXT_BLOCKER 候选（不自动开始）：**TEMPORAL_LEARNED_TRACKER（利用中间帧；注意 CoTracker CC-BY-NC 许可需另选合规实现）** 或 **LOCAL/GLOBAL/UNSURE 证据层级重构**。

## 5. 全链 Anchor 汇总（对照）
feature 12/36 · GFTT 17/36 · patch 7/36 · STRUCT01 0/36 · OBJ01 0/36 · **DENSE01 0/36**（但 MNN 全覆盖、拟合稳健——端点对应精度是瓶颈而非召回）。

## 产物
reports/storage/TREECUT_CAM01_DENSE01_ENV_AUDIT.json · _CONFIG.json · _MODEL_PROVENANCE.json · _MATCH_MATRIX.json ·
_HOLDOUT_VALIDATION.json · _STRUCTURAL_VALIDATION.json · _CONSENSUS.json · _TARGET_DIAGNOSTIC.json ·
_NEG_TARGET_CONTROL.json · _RESULT.json · _CANDIDATE.json · _GALLERY.html · scripts/posta3_cam01_dense01.py
