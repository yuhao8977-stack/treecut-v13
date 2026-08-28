# VISION_STAGE3_CANDIDATE_V2 — 逐字段状态（Stage3 Candidate，非 Bundle V2）

> 状态：STAGE3 CANDIDATE（参数/阈值已冻结于 Stage3 DEV；**暂不创建 Bundle V2**）
> 冻结纪律：仅 Calibration333 + Stage3 60 DEV；Fresh Holdout V1 只作 KNOWN BENCHMARK 参考，不用于选择。
> 冻结后才允许：VISION_MODEL_BUNDLE_V2 → lock → FRESH_HOLDOUT_V2。

## 逐字段

| 字段 | Primary | Fallback | DEV 指标 | Support | 状态 |
|---|---|---|---|---|---|
| people_presence | **PeoplePresenceAnalyzerV2**（YOLOv8n person, conf=0.70） | SigLIP | 合并387段 F1 94.2 / bacc 86.4；CAL333 F1 94.6 / STAGE3 F1 92.1 | YES 305 / NO 114 | **READY_CANDIDATE** |
| action_sequence | **SemanticActionAnalyzerV1**（规则基） | — | OPEN_DRAWER P100/R18/F1 30.8；PULL_OUT F1 23.9；其余原子 F1≈0（ASR 覆盖不足） | 8 类 ≥10 | **EXPERIMENTAL**（V1 规则基需补视觉状态证据） |
| component | SigLIP Top3+gap（V2） | — | 合并 F1 35.9 / macroF1 53.2 | DRAWER 79 / TRACK_SOCKET 87 | **READY_CANDIDATE**（V2 成立） |
| function | SigLIP Top3+gap（V2） | — | 合并 F1 33.2 / macroF1 52.6 | STORAGE/EXTENDABLE/POWER… | **READY_CANDIDATE**（V2 成立） |
| material | SigLIP V1（阈值0.06） | — | F1 22.2（MIXED/弱） | 岩板 386 / 实木 1 | **EXPERIMENTAL / FALLBACK** |
| shot_role | SigLIP V1 | — | F1 36.9 / pred_avg 7.0（过预测） | 丰富 | **EXPERIMENTAL**（V3 压缩未达门槛） |
| product_family | SigLIP | — | Cal333 52.7% / STAGE3 72.7% vs Holdout 51.7% | ISLAND 主导 | **READY_CANDIDATE**（无退化） |
| scene_family | SigLIP | — | FACTORY 主导（97%+） | FACTORY 380 / CUSTOMER_HOME 2 | **LIMITED**（长尾素材库缺失） |
| product_variant | SigLIP | — | EXTENDABLE/STANDARD | FLOATING/FLOOR=0 | **LIMITED**（LIBRARY_GAP） |

## 状态汇总

- **READY_CANDIDATE**：people_presence(V2)、component(V2)、function(V2)、product_family
- **EXPERIMENTAL**：action_sequence(V1 规则基)、material(V1)、shot_role(V1)
- **LIMITED**：scene_family、product_variant（受素材库长尾缺失限制）
- **FAILED**：无
- **LIBRARY_GAP**：FLOATING/FLOOR 变体、奢石/大理石/不锈钢/玻璃、INSTALLATION_SITE、CLOSE_DRAWER（0 候选）

## 冻结参数

| 参数 | 值 |
|---|---|
| People threshold | **0.70**（Stage3 DEV 冻结） |
| component/function | V2（Top3, gap 0.10, min 0.02） |
| material / shot_role | V1（阈值 0.06） |
| Semantic Action | V1 规则基（EXPERIMENTAL） |

## 下一步（冻结 Bundle V2 前必须）

1. TRACK B 已发现：OPERATE_SOCKET 1940 候选 / CUSTOMER_HOME 2367 / SOLID_WOOD 801（唯一 asset 908/819/335）→ **候选充足，值得小批验证 precision**
2. 3 条 QA 裁决完成 → 干净真值进入 Semantic Action 开发
3. SemanticActionAnalyzerV1 需补视觉状态变化证据（B2 发现器同理）
4. 全部冻结后才建 VISION_MODEL_BUNDLE_V2 → FRESH_HOLDOUT_V2
