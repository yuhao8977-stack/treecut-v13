# Human Label Reliability V1 — 人工标签可靠性报告

- **日期**：2026-08-27 18:55 ｜ 方法：第一轮人工（v1）与独立二次盲复核（v2）逐字段交叉比对
- **样本**：60 条 SECOND_REVIEW_V1；42 条 v1 已标注（可比）、18 条 v1 未标注（v2 补齐）
- **只读审计**；v2 未覆盖 first 答案与 AI 答案，独立性成立

## 1. 三层一致率（42 条可比子集）

| 字段 | raw 精确 | 归一化 | 层级兼容 | 判定 |
|---|---|---|---|---|
| scene | 0.0% | 95.2% | 95.2% | 高可靠（词典归一化后） |
| product | 83.3% | 83.3% | 97.6% | 高可靠 |
| material | 97.6% | 97.6% | 97.6% | 高可靠（最稳） |
| function | 35.7% | 90.5% | 90.5% | 高可靠（归一化后） |
| action | 0.0% | 61.9% | 61.9% | 偏弱 |
| shot_type | 4.8% | 4.8% | 4.8% | 不可比（词典重构） |
| people_presence | 92.9% | 92.9% | 92.9% | 高可靠 |

**Pooled（294 格）**：raw 44.9% → 归一化 75.2% → 层级 77.2%。
**去 shot_type 的 6 字段（252 格）**：归一化 **86.9%**、层级 **89.3%**。

## 2. 真分歧明细（67 格）

字段分布：shot_type 40, action 16, function 4, people_presence 3, scene 2, product 1, material 1.

| segment | 字段 | v1 | v2 |
|---|---|---|---|
| `0083d4f7…` | action | 拉出/展开 | 静态展示 |
| `0083d4f7…` | shot_type | 中景 | 空间扫镜 |
| `02846d5f…` | shot_type | 中景 | 人物讲解 |
| `09d52700…` | shot_type | 近景 | 人物讲解 |
| `09f514b8…` | shot_type | 近景 | 人物讲解+功能演示 |
| `1c158078…` | shot_type | 特写 | 其他-产品扫镜 |
| `20971889…` | action | 拉出/展开 | 关闭抽屉 |
| `20971889…` | shot_type | 中景 | 功能演示 |
| `217f7f63…` | action | 其他 | 人物讲解 |
| `217f7f63…` | shot_type | 全景 | 人物讲解 |
| `311d492a…` | shot_type | 中景 | 人物讲解 |
| `3dfe55e5…` | action | 收纳/关闭 | 打开抽屉+关闭抽屉 |
| `3dfe55e5…` | shot_type | 中景 | 人物讲解 |
| `3fdb955f…` | shot_type | 全景 | 人物讲解 |
| `4379f2ae…` | action | 拉出/展开 | 静态展示 |
| `4379f2ae…` | shot_type | 特写 | 产品静态拍摄镜头 |
| `49e0fded…` | shot_type | 近景 | 功能演示+人物讲解 |
| `4c9c0993…` | function | 抽屉 | 用电 |
| `4c9c0993…` | shot_type | 其他 | 人物讲解+功能演示 |
| `55d1f1be…` | shot_type | 近景 | 人物讲解 |
| `5689b909…` | shot_type | 近景 | 人物讲解+功能演示 |
| `5e8708a3…` | shot_type | 特写 | 功能演示 |
| `5fe361e7…` | action | 拉出/展开 | 缩回+拉出 |
| `5fe361e7…` | shot_type | 全景 | 功能演示 |
| `64053830…` | shot_type | 中景 | 人物讲解+功能演示 |
| `7269064d…` | action | 收纳/关闭 | 静态展示 |
| `7269064d…` | shot_type | 特写 | 空间扫镜 |
| `7269064d…` | people_presence | no | yes |
| `7426f81d…` | shot_type | 中景 | 功能演示 |
| `8cd9ae96…` | action | 拉出/展开 | 静态展示 |
| `8cd9ae96…` | shot_type | 特写 | 空间扫镜 |
| `92d95d89…` | shot_type | 全景 | 功能演示 |
| `a077c5a0…` | scene | 展厅 | 工厂展示区 |
| `a077c5a0…` | shot_type | 中景 | 人物讲解 |
| `a3c73748…` | shot_type | 近景 | 功能演示 |
| `a60b0d13…` | shot_type | 其他 | 空间扫镜 |
| `a654170c…` | action | 其他 | 关闭抽屉 |
| `a707191d…` | shot_type | 特写 | 功能演示 |
| `af2874bb…` | shot_type | 近景 | 人物讲解 |
| `b7cb2548…` | action | 拉出/展开 | 拉出+缩回 |

**解读**：
- action 16 格：v2 原子动作 vs v1 粗类 的映射边界 + 真实分歧并存（如 讲解/演示→静态展示、拉出/展开→关闭抽屉）
- shot_type 40 格：词典重构，非分歧（见 ANNOTATION_TAXONOMY_AUDIT §2）
- people 3 格：yes/no 判断差异（人物在画面边缘/背影的判定）
- scene 2 格、product 1 格、material 1 格、function 4 格：零星真分歧，<10% 水平

## 3. 可信度分层证据

- v2 `human_confidence` 分布：MEDIUM 60（100%）→ **无 HIGH/LOW 分层样本，无法验证"置信度越高越可靠"**（OBSERVATION）
- v2 `review_status` 分布：REVIEWED 60 → 无 GOLD/NEEDS_SECOND_REVIEW
- CANDIDATE：后续复核 UI 必须强制选择 human_confidence 并随机混入已知答案做金标准自检

## 4. 可靠性结论

1. **主口径**：6 语义字段归一化一致率 86.9% → v1 人工标签**可作为校准真值**
2. **弱项**：action（61.9%）与 shot_type（不可比）不可直接当真值用，Phase 3 需重建词典后重标
3. **v2 补齐的 18 条**：单次审核证据（16 条有效 + 2 条空提交），可靠性与 42 条可比子集不同级，已在 CALIBRATION 清单中标注证据分层
4. **坏段**：`b3757ee9…`（视频无法播放）应走坏段清理流程（OBSERVATION）

## 5. 使用建议（CANDIDATE）

- CALIBRATION_CORPUS_V1 学习时：先学 42 双盲段 → 274 单审段 → 16 v2 补齐段，按证据等级加权
- 所有涉及 action/shot_type 的学习样本需在 Schema V2 词典统一后重新编码
