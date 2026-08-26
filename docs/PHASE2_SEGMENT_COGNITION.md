# TreeCut Phase 2 — Segment Cognitive Layer 审计总报告

> 阶段: Phase 2（镜头级认知层）| 日期: 2026-08-26
> 前置: Phase 0 PASS / Phase 1 PASS
> 状态: 完成，等待架构监工验收 | 未进入 Phase 3

---

## 目录

1. [执行摘要](#一执行摘要)
2. [0. Phase 前置保护](#二0-phase-前置保护)
3. [1. 75 个无 Segment Asset 审计](#三1-75-个无-segment-asset-审计)
4. [2. Segment 边界审计](#四2-segment-边界审计)
5. [3-4. 认知数据模型 + L1/L2/L3 分层](#五3-4-认知数据模型--l1l2l3-分层)
6. [5-6. Evidence Builder + 技术质量](#六5-6-evidence-builder--技术质量)
7. [7-8. 业务语义 + Evidence/Confidence](#七7-8-业务语义--evidenceconfidence)
8. [9-11. 300 校准集 + 审核 UI + baseline 冻结](#八9-11-300-校准集--审核-ui--baseline-冻结)
9. [12-13. Metrics + 边界/认知分开评价](#九12-13-metrics--边界认知分开评价)
10. [14-16. 测试 + Service + Versioning](#十14-16-测试--service--versioning)
11. [17. Migration 0003](#十一17-migration-0003)
12. [19-20. 验收报告与硬门槛](#十二19-20-验收报告与硬门槛)
13. [遗留问题与风险](#十三遗留问题与风险)

---

## 一、执行摘要

Phase 2 目标：建立 Segment 认知层——让系统知道"一个镜头里发生了什么"。
**未对 41814 全量跑 AI，仅 300 样本校准集 + 架构建设 + 小样本验证。**

| 验收项 | 结果 |
|---|---|
| git commit | 见第十二章 |
| migration version | **0003**（semantic_annotations + human_annotations） |
| pytest | **73 passed / 0 failed** |
| 新增测试 | 10 个（Phase 2） |
| coverage（segment_cognition） | **81%** |
| DB integrity | ok |
| 300 样本标注 | **300/300 成功** |
| 技术质量可计算 | 299/300（平均 77.4 分） |

**关键成果**：
- semantic_annotations（L2）+ human_annotations（L3）正式分层，不可覆盖
- SegmentEvidenceBuilder 按 segment 时间过滤 ASR/OCR/关键帧（验证通过）
- SegmentTechnicalQuality 基于关键帧 sharpness/brightness 真实计算
- 300 校准集（CALIBRATION_SET_V1）AI 基线已生成
- Segment 认知审核 UI 建立
- 75 个无 Segment Asset 根因查明（pipeline 遗漏，非损坏）

---

## 二、0. Phase 前置保护

| 项 | 值 |
|---|---|
| git 工作树 | 干净 |
| 当前 commit | f827a47（Phase1 末态） |
| Phase2 备份 | `backups/materials_phase2_20260826_164057.db`（329.02MB） |
| 备份完整性 | ✅ ok（原库+备份库） |
| manifest | `PHASE2_BACKUP_MANIFEST.json` |

---

## 三、1. 75 个无 Segment Asset 审计

**详见 `docs/NO_SEGMENT_ASSET_AUDIT.md`**

### 结论：全部为 Pipeline 遗漏（Segment 生成遗漏），非损坏视频。

| 分类 | 数量 |
|---|---|
| A. 损坏/不可解码 | **0**（文件均存在，0 字节=0，median 6.2MB） |
| B. 极短视频 | 0 |
| C. Scene 阶段失败 | 0（scene:DONE 72 / PROCESSING 3，无 FAILED） |
| D. **Segment 生成遗漏** | **75** |
| E. 未知 | 0 |

### 根因链

```
全库 probe DONE = 0（历史 pipeline 从未执行 probe）
  → assets.duration/宽高/fps 全 0
  → SceneDetector 无时长输入 → 无法生成 segment
  → keyframe SKIPPED（75）→ 无 segment
```

### 修复方案（等待后续 Phase 安全处理）

1. 对 75 个 asset 执行 probe（ffprobe）
2. 重跑 scene 切分 → 生成 keyframe + segment
3. 预期恢复 72+ 个

**本 Phase 仅审计 + 标记，未直接补 Segment。**

---

## 四、2. Segment 边界审计

**详见 `docs/SEGMENT_BOUNDARY_AUDIT.md`**

### 300 样本构成

| 组 | 数量 |
|---|---|
| fixed_5s（duration=5000ms） | 166 |
| contentdetector（非 5s） | 134 |
| ASR+OCR / 仅ASR / 仅OCR / 双弱 | 147 / 82 / 33 / 38 |

### 关键发现

| 指标 | 值 |
|---|---|
| 全库 5s 段占比 | **56.6%**（23658/41814） |
| 5s 组平均关键帧 | 7.3 |
| 检测器组平均关键帧 | 6.74 |
| 动作截断风险 | 5s 组全存在（真实样例证实 ASR 长段横跨边界） |

### 结论

- 5s 固定切分占比高 → **动作截断风险大**（需 Phase 3 视觉时序确认）
- 本 Phase **未重切**，边界精确审计延至 Phase 3

---

## 五、3-4. 认知数据模型 + L1/L2/L3 分层

### semantic_annotations（L2，versioned）

```sql
annotation_id, target_type(segment|asset), target_id,
scene, product, material, function, action, shot_type,
people_presence, product_visibility, product_completeness,
quality_score, content_role, business_value,
confidence, evidence_refs_json,
model_name, model_version, prompt_version, knowledge_version, algorithm_version,
status(candidate|validated|superseded), created_at, superseded_by
```

### human_annotations（L3，单独保存）

```sql
adjudication_id, annotation_id, target_type, target_id,
scene, product, material, function, action, shot_type,
people_presence, product_visibility, quality_score,
comment, operator, created_at
```

### 分层原则（宪法 3）

| 层 | 存储 | 可被覆盖？ |
|---|---|---|
| L1 机器证据 | ASR/OCR/keyframes/scene 原始表 | 否 |
| L2 AI 解释 | semantic_annotations | 仅 superseded（versioned） |
| L3 人工裁决 | human_annotations | 否（与 L2 分离） |

**验证**：测试 `test_human_adjudication_does_not_overwrite` 证实 L3 修正不覆盖 L2。

---

## 六、5-6. Evidence Builder + 技术质量

### SegmentEvidenceBuilder

按 segment 时间范围聚合（验证通过）：

| 证据 | 过滤方式 | 验证 |
|---|---|---|
| ASR | transcripts.start_ms/end_ms 重叠检测 | ✅ test_evidence_asr_time_filtered |
| OCR | frame_timestamp_ms ±1.5s | ✅ test_evidence_ocr_time_filtered |
| 关键帧 | timestamp_ms ±1.5s | ✅ test_evidence_keyframes_filtered |
| 场景语义 | asset 级 | ✅ |
| asset 上下文 | content_classification | ✅ |

**关键验证**：transcripts.segment_id 全 NULL（0/51516），但 EvidenceBuilder 用时间重叠正确过滤——不把一个 60s asset 的 ASR 全塞给 4s segment。

### SegmentTechnicalQuality

基于 segment 内关键帧 sharpness/brightness 聚合：

| 指标 | 值 |
|---|---|
| 可计算 | 299/300 |
| 平均质量 | 77.4 |
| 最小/最大 | 19.6 / 88.1 |
| 黑帧率>0 样本 | 0 |
| 未实现（PARTIAL） | contrast/motion/遮挡（标注不伪造） |

---

## 七、7-8. 业务语义 + Evidence/Confidence

### 支持字段（L2）

scene / product / material / function / action / shot_type / people_presence

### 规则引擎（无 LLM）

- 关键词规则 + asset 级 CLIP 标签兜底
- **无证据 → UNKNOWN（合法，不强行猜）**

### Evidence 保存

每个判断保存 evidence_refs_json：
```json
{"asr_hits": [[start, text]], "asr_text": "...", "ocr_text": "...",
 "keyframes": [timestamps], "clip_tags": [...]}
```

### Confidence（修正后）

| 条件 | confidence |
|---|---|
| 全部字段 UNKNOWN | 0.45（降，避免"有声音就高置信"假象） |
| 有 ASR 命中 | 0.85 |
| 仅 asset 级文本 | 0.70 |
| 仅 CLIP 标签 | 0.55 |
| 双弱 | 0.35 |

---

## 八、9-11. 300 校准集 + 审核 UI + baseline 冻结

### 300 校准集（CALIBRATION_SET_V1）

- 分层：5s 166 / 检测器 134；ASR+OCR 147 / 仅ASR 82 / 仅OCR 33 / 双弱 38
- 全部 300 已生成 AI 基线（baseline_prediction 落库 semantic_annotations）
- 样本清单：`segment_boundary_sample_300.json`

### 审核 UI（`--segment-cognition-ui`）

- 左：segment 信息 + 视频播放（±3s 上下文）
- 中：L1 机器证据（不可改）
- 右：L2 AI 判断（只读绿）+ L3 人工确认（下拉，保存最终业务值）
- 人工裁决写入 human_annotations，不覆盖 L2

### baseline 冻结

- 300 条 AI 结果已先生成（candidate 状态），人工审核**后置进行**
- 未边审核边改规则（本轮规则迭代在审核前完成）

---

## 九、12-13. Metrics + 边界/认知分开评价

### L2 认知统计（300 样本）

| 字段 | 识别率 | UNKNOWN 率 |
|---|---|---|
| scene | 8.3% | 91.7% |
| product | 38.0% | 62.0% |
| material | 1.3% | 98.7% |
| function | **17.0%** | 83.0% |
| action | 8.7% | 91.3% |

**UNKNOWN 率高是真实的**：大多 segment ASR 是讲解话术（无功能词）+ asset 级 scene_semantics 覆盖仅 0.63%（141/22465）。诚实标注，不猜。

### confidence 分布

| confidence | 数量 |
|---|---|
| 0.45（全 UNKNOWN） | 147 |
| 0.55 | 1 |
| 0.70 | 14 |
| 0.85（有 ASR 命中） | 138 |

### 边界 vs 认知分开评价（宪法）

```
semantic_correct = YES（AI 识别伸缩动作）
boundary_usable  = NO（segment 切了一半动作）
→ 分开记录，不混成一个准确率
```

---

## 十、14-16. 测试 + Service + Versioning

### 新增测试（`tests/test_phase2_cognition.py`，10 用例）

| 组 | 用例 |
|---|---|
| Evidence | ASR 时间过滤 / OCR 时间过滤 / 关键帧过滤 / 无 ASR/OCR / 非法 segment |
| L2 | 从证据推断 / UNKNOWN 合法 / versioning supersede |
| L3 | 人工裁决不覆盖 L2 |
| 技术质量 | 可计算 / 无帧返回 -1（不伪造） |

### pytest 结果

| 指标 | 值 |
|---|---|
| 总测试 | **73** |
| 通过 | **73** |
| 失败 | 0 |
| coverage（segment_cognition） | **81%** |

### Service Layer

- `services.segment_cognition.py`：SegmentCognitionService（L2）+ SegmentEvidenceBuilder + SegmentTechnicalQuality
- `services.segment_cognition_ui.py`：审核 UI
- CLI 仅薄适配（`--segment-cognition-ui` / `--segment-annotate`），无业务 SQL

### Versioning（宪法 4）

| 字段 | 值 |
|---|---|
| model_name | rules+clip-v1 |
| model_version | 1.0 |
| prompt_version | **NONE**（无 LLM，明确标注） |
| knowledge_version | knowledge-v1 |
| algorithm_version | segment-cognition-v1 |

---

## 十一、17. Migration 0003

| 项 | 值 |
|---|---|
| 文件 | `migrations/0003_segment_cognition.sql` |
| schema_migrations | v0003（commit f827a47） |
| 新增表 | semantic_annotations / human_annotations（+ 索引） |
| integrity | ok（49 → 51 表） |
| 方式 | MigrationManager.apply_pending()（未绕过） |

---

## 十二、19-20. 验收报告与硬门槛

### 验收硬门槛核对

| [ ] 门槛 | 状态 |
|---|---|
| Segment 认知数据模型成立 | ✅ |
| L1/L2/L3 彻底分开 | ✅（测试证实） |
| Segment Evidence Builder 成立 | ✅ |
| ASR/OCR 严格按 Segment 时间过滤 | ✅（测试+真实样例） |
| AI 判断保存 Evidence | ✅（evidence_refs_json） |
| AI 判断保存完整 Version | ✅（5 版本字段，prompt=NONE） |
| UNKNOWN 成为合法结果 | ✅（不猜） |
| 300 条校准集完成 | ✅（AI 基线已冻结） |
| 人工审核可保存最终业务值 | ✅（UI + L3 表） |
| Segment 边界问题规模被量化 | ✅（56.6% 5s 段） |
| 75 个无 Segment Asset 原因查明 | ✅（pipeline 遗漏） |
| 新测试全部通过 | ✅ 73/73 |
| DB integrity = ok | ✅ |
| 没有全量重跑 | ✅（仅 300） |
| 没有进入 Phase 3 | ✅ |

### 交付物

| 文件 | 说明 |
|---|---|
| `docs/PHASE2_SEGMENT_COGNITION.md` | 本报告 |
| `docs/NO_SEGMENT_ASSET_AUDIT.md` | 75 无 Segment 审计 |
| `docs/SEGMENT_BOUNDARY_AUDIT.md` | 边界审计 |
| `PHASE2_BACKUP_MANIFEST.json` | 备份清单 |
| `migrations/0003_segment_cognition.sql` | Migration 0003 |
| `src/treecut/services/segment_cognition.py` | L2 服务 + Evidence + 质量 |
| `src/treecut/services/segment_cognition_ui.py` | 审核 UI |
| `tests/test_phase2_cognition.py` | 10 测试 |

---

## 十三、遗留问题与风险

| 项 | 说明 | 处理 |
|---|---|---|
| UNKNOWN 率高（scene 91.7%） | scene_semantics 覆盖 0.63%，ASR 多为讲解话术 | Phase 3 视觉时序 + Phase 4 知识库 |
| 5s 段占比 56.6% | 动作截断风险 | Phase 3 边界审计 |
| 75 无 Segment Asset | pipeline 遗漏 | Phase 3 probe+scene 重跑 |
| 技术质量 contrast/motion 未实现 | 需视觉时序 | Phase 3 |
| 300 样本 AI 准确率未测 | 待人工审核后计算 | 审核后 Metrics 更新 |
| material 识别 1.3% | 材质词在 ASR 中少（多在画面） | Phase 3 CLIP 增强 |

---

**Phase 2 完成。按宪法 14 条，未进入 Phase 3，等待架构监工验收。**
