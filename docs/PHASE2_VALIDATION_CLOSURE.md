# TreeCut Phase 2 Validation Closure —— Segment 认知人工验证收尾

> 日期: 2026-08-26 | 架构监工判定: ENGINEERING=PASS / VALIDATION=PARTIAL
> 状态: **验证体系已就绪，等待人工审核 300 条 Segment**
> 禁止进入 Phase 3

---

## 一、本阶段目标

不新增 AI 能力，不优化规则，不修改 300 条 baseline_prediction。
只完善验证体系 + 完成只读审计，然后等待人工审核。

## 二、已完成的收尾工作

### 1. Baseline 冻结（CALIBRATION_SET_V1）

`CALIBRATION_SET_V1_MANIFEST.json`：

| 项 | 值 |
|---|---|
| set | CALIBRATION_SET_V1 |
| git_commit | 5c99564 |
| model_name/version | rules+clip-v1 / 1.0 |
| knowledge_version | knowledge-v1 |
| algorithm_version | segment-cognition-v1 |
| sample_manifest | segment_boundary_sample_300.json（seed=42） |
| annotations | 300（candidate 状态） |
| policy | **禁止重新生成/覆盖** |

### 2. 术语修正（已完成）

| 原表述 | 修正为 |
|---|---|
| scene 8.3% "识别率" | **prediction_coverage（非 UNKNOWN 率）** |
| product 38% | prediction_coverage |
| 其余字段同理 | prediction_coverage / non_unknown_rate |
| "准确率" | **禁止**（无人工真值前不称 accuracy） |

### 3. Migration 0004：segment_boundary_reviews

```sql
review_id, segment_id, annotation_id,
boundary_start_ok, boundary_end_ok, action_complete, semantic_complete,
cut_mid_action, cut_mid_sentence, usable_as_edit_unit,
boundary_comment, operator, created_at
UNIQUE(segment_id, annotation_id)
```

### 4. fixed_5s provenance 核验结论

| 证据 | 结果 |
|---|---|
| segments.algorithm_version | 全部 `scenedetect-0.7-contentdetector-uniform`（无区分标志） |
| processing_history | 仅记录"场景切分完成"，无 fallback 原因 |
| 5s 段覆盖 asset | 16422/22390（广泛分布） |

**结论：无法 100% 证明 fallback 来源。** 报告术语改为 **"56.6% 5s-like segments"**。
`segments.generation_method` 字段已加入（默认 UNKNOWN，供未来记录）。

### 5. 75 无 Segment Asset 只读 ffprobe（已完成，只读未写回）

**75/75 全部可解码且含视频流** → 全部归类 `PIPELINE_OMISSION_CONFIRMED`。

| 项 | 值 |
|---|---|
| 可解码含视频流 | 75/75 |
| 时长 | min 0.05s / median 0.64s / max 17.17s |
| <1s | **70/75** |
| <3s | 70/75 |

**根因修正**：真正原因是**视频极短**（70/75 <1s）+ SceneDetector `min_scene_len_sec=1.0` 门槛过滤
→ 无法生成 segment。（此前推断"probe 未执行"为方向对、机制不精确。）

结果存 `no_segment_ffprobe_audit.json`（含 8 字段/条）。

### 6. Evidence Overlap Audit（只收数据，不调阈值）

`evidence_overlap_audit.json`（300 样本）：

| overlap_ratio | 数量 |
|---|---|
| 强（≥0.6） | 103 |
| 中（0.3-0.6） | 111 |
| 弱（<0.3） | 10 |
| 无重叠 | 76 |

字段：transcript_start/end, segment_start/end, overlap_ms, overlap_ratio。

### 7. Technical Quality 命名

- UI/文档统一显示 **"Technical Quality V1 (Partial)"** / "基础技术质量"
- 明确仅 sharpness/brightness；contrast/motion/stability/遮挡 未实现（不冒充整体质量）

### 8-9. 审核 UI 升级（已完成）

- **Boundary 审核区**：7 项（起点/终点/动作完整/语义完整/动作切断/语句切断/可作为剪辑单位）
- **进度显示**：已审核 X/300 + 上一条/下一条/跳过
- 人工值保存至 human_annotations（不覆盖 L2）+ segment_boundary_reviews

### 10. 审核期间禁止学习（政策声明）

人工审核第一条至 300 条完成期间，**禁止**：
- 修改 industry 规则 / confidence / EvidenceBuilder / 知识库 / CLIP
- 重新生成 baseline / 自动 learning / weight update

### 11-12. 验证报告命令（已就绪）

```
python -m treecut.main --segment-validation-report
```
生成 `docs/PHASE2_VALIDATION_REPORT.md`，包含：
真实 Accuracy / F1 / UNKNOWN / Confusion Matrix / Boundary Metrics /
Quality Metrics（MAE/相关性）/ Evidence Error Analysis。

## 三、当前状态与等待事项

```
✅ 验证体系就绪（UI/表/报告命令/只读审计）
⏳ 等待人工审核 300 条 Segment
❌ 未计算真实准确率（无人工真值）
❌ 未进入 Phase 3
```

**请开始人工审核 300 条 Segment**（打开 Segment Cognitive Review，今天 100 / 明天 100 / 后天 100）。
300 条完成后运行 `--segment-validation-report`，生成 PHASE2_VALIDATION_REPORT.md 供架构监工验收。

---

*本收尾未修改 baseline、未优化规则、未全量重跑。*
