# Phase 3 多模态认知架构（Stage 1 实现）

- **日期**：2026-08-28 10:39 ｜ 实现：`src/treecut/services/visual_cognition.py`（统一入口 `VisualCognitionPipeline`）

## 1. 管线

```text
Segment
  └─ FrameSampler（start/25/50/75/end + 运动自适应）
       ├─ StaticVisualCognition ── scene_family/shot_scale/people/material/product
       ├─ TemporalActionAnalyzer ── action_group + action_sequence（帧差能量）
       ├─ TechnicalQualityV2 ──── sharpness/brightness/contrast/motion/stability/black/exposure
       └─ ASR（asset 级 transcripts）+ OCR（frame 级 ocr_text）
            └─ SegmentMultimodalEvidence（per-field 融合）
                 └─ EvidenceGate（per-field sufficiency）
                      └─ ConfidenceGate（路由，不称概率）
```

## 2. per-field 融合权重（冻结口径）

| 字段 | 视觉 | ASR | OCR | 说明 |
|---|---|---|---|---|
| material | 0.8 | 0.2 | — | 视觉证据权重最大 |
| function | 0.5 | 0.5 | — | 视觉 + ASR |
| action | temporal 0.7 | 0.3 | — | 时序 > ASR |
| scene | 0.85 | 0.15 | — | visual >> ASR |
| product | 0.6 | 0.4 | — | visual + ASR |
| shot_scale | 1.0 | — | — | visual only |
| shot_role | 0.5 | — | 0.5 | 视觉 + OCR |
| component | 0.3 | 0.7 | — | ASR 主导 |

## 3. Evidence Sufficiency（per-field）

SUFFICIENT（score≥0.3 且标签非空）→ CHEAP_END
PARTIAL（有标签但 score 低）→ ADD_FRAMES
WEAK（单值 UNKNOWN 但低分）→ STRONG_VISION
CONFLICT（预留多源冲突位）→ STRONG_VISION_WITH_EXPLANATION
MISSING（无任何标签）→ UNKNOWN

## 4. Confidence 纪律

- `model_score` / `evidence_sufficiency` / `fusion_score` **三值分离**，禁止合并为单一概率
- 命名：HEURISTIC_CONFIDENCE_V1（历史保留）；Phase 3 起 model_score 仅作相对排序
- 校准（ECE/Brier/reliability diagram）留到真实模型输出产生后

## 5. 数据流与版本

- 每字段携带 `model_version=opencv-heuristic-v0.1` + `frame_refs`（可追溯）
- 输出写库前经 Gate 路由；MISSING 字段 → UNKNOWN（禁止伪造）
- canonical truth 升级走 `new_version()`（V3 裁决后），history 永久保留

## 6. 已知局限（诚实）

1. product_family 视觉原型极弱（主体形状启发式），评估 0%
2. material/shot_role 无视觉识别能力（原型无法区分岩板/实木等）
3. people 恒 NO（haar cascade 文件缺失 → 人脸检测不可用）
4. 上述局限是 Stage 1 预期——引入真实视觉模型 + 94 条人工数据后迭代
