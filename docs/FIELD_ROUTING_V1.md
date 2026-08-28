# FIELD_ROUTING_V1 — 字段级认知路由（Stage 2 Pre-Holdout）

- **日期**：2026-08-28 17:11 ｜ git `ed9907c` ｜ 原则：**整体决策不退化**——每字段采用当前最可靠路径，禁止"SigLIP 接管一切"
- 数据：CALIBRATION_CORPUS_V2（333，dev-set；**accuracy 受极端偏科扭曲，仅供相对比较**）

## 每字段路由

| 字段 | primary_provider | fallback_provider | status | 依据（dev, accuracy） |
|---|---|---|---|---|
| scene_family | SigLIP(EN prompt) | 旧 rules+clip | **EXPERIMENTAL** | SigLIP 27.1% > baseline 3.9%；但 Always-FACTORY trivial=98.2%（偏科）→ 覆盖率 55.6% 真实信号，accuracy 需 holdout 验证 |
| product_family | **SigLIP(EN)** | 旧 rules+clip | **READY_FOR_HOLDOUT** | 42.6% > baseline 28.8%（真实超旧方案；trivial=99.4% ISLAND 需 holdout 校准） |
| product_variant | 旧路径/UNKNOWN gate | SigLIP | **FALLBACK** | 无 variant 独立视觉评估；避免凭空猜测变体 |
| material[] | SigLIP | — | **EXPERIMENTAL** | microF1 22.1%；岩板 P99.5/R65/F1 78.6；**实木/奢石/大理石等 INSUFFICIENT_SAMPLE（support 0-1）** |
| component[] | 融合（ASR+SigLIP） | SigLIP | **EXPERIMENTAL** | microF1 24.4%（DRAWER F1 49.1 / TRACK_SOCKET 36.0）；trivial 30.3% |
| function[] | 融合（ASR+SigLIP） | SigLIP | **EXPERIMENTAL** | microF1 21.5%（STORAGE F1 55.7 / EXTENDABLE 27.3）；trivial 38.1% |
| shot_scale | SigLIP | — | **EXPERIMENTAL** | 25.8%（trivial 27.6%）；覆盖 52.7%，真实信号 |
| shot_role[] | SigLIP | — | **EXPERIMENTAL** | microF1 19.9%（PERSON_TALKING F1 68.7）；trivial 62.2%(UNKNOWN) |
| people_presence | **旧方案** | SigLIP | **FALLBACK** | baseline 19.6% > SigLIP 6.0%（**SigLIP 退化，禁止 primary**） |
| action_group/sequence | 融合（运动+静态+ASR） | — | **EXPERIMENTAL** | 光流 action_group 3.3%（非语义识别器）；motion 仅作 evidence |
| product_visibility | SigLIP | — | EXPERIMENTAL | 未纳入 333 真值 |

## 状态语义
- READY_FOR_HOLDOUT：dev 上超过既有最优，可进 30 条考试
- EXPERIMENTAL：有真实视觉信号但未稳定/未超 trivial（偏科下 accuracy 不可靠）→ 进 holdout 但结果单独报告
- FALLBACK：保留旧路径为 primary（避免退化）
- INSUFFICIENT_SAMPLE：样本 <5，禁止宣称类别能力

## 防退化规则
任何字段 Stage2 低于既有可靠 baseline → primary 自动回退旧路径（如 people、product_variant）。
