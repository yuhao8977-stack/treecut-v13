# TreeCut Segment 完整性报告（SEGMENT_INTEGRITY_REPORT）

> Phase: 1 | 日期: 2026-08-26
> 数据: materials.db segments 表（生产库实时查询）

---

## 一、核心结论

**Segment 数据质量优秀：8 项检查中 7 项 0 异常，1 项为历史遗留（质量分未评分）。**

| # | 检查项 | 结果 | 状态 |
|---|---|---|---|
| 6.1 | segment_id 唯一性 | 0 重复（41814 条全唯一） | ✅ PASS |
| 6.2 | asset_id 外键有效性 | 0 orphan | ✅ PASS |
| 6.3 | start_ms < end_ms | 0 非法 | ✅ PASS |
| 6.4 | duration_ms > 0 | 0 非法 | ✅ PASS |
| 6.5 | 时间范围 ≤ asset 真实时长 | 0 超界（+2s 容差） | ✅ PASS |
| 6.6 | 同 asset 重复 [start,end] | 0 组 | ✅ PASS |
| 6.7 | orphan segment | 0 | ✅ PASS |
| 6.8 | quality_score 未评分 | **41814 (100%)** | ⚠️ 历史遗留 |

---

## 二、详细数据

### 基础统计

| 项 | 值 |
|---|---|
| segments 总数 | **41814** |
| 覆盖 asset 数 | 22390 |
| assets 总数 | 22465 |
| media_files 总数 | 28096 |
| orphan assets（无 media） | 0 |
| orphan segments（无 asset） | 0 |

### 时长分布（已审计）

| 指标 | 值 |
|---|---|
| 平均时长 | 4.19s |
| 中位数 | 5.0s |
| P10 | 2.0s |
| P90 | 5.0s |

### 生成方式

- ContentDetector(threshold=27) 检测优先，失败/不可用回退均匀分段
- 5s 聚集提示大量素材走固定兜底（P9 降级提交 73b53a4）
- `scenes/detector.py` ALGORITHM_VERSION = "scenedetect-0.7-contentdetector"

---

## 三、发现与处理

### ⚠️ 6.8 quality_score 全 0（100% 未评分）

- 现象：segments.quality_score 全部为 0
- 原因：历史分段流程未写入质量分（P2 分段时 quality_score 未实现评分逻辑）
- 处理：**仅标记，不删除、不修改**（宪法：异常只报告）
- 影响：Phase 2 Segment 认知时需补充质量维度；当前不影响 ID 追溯

### 生成方式混杂（scene 级 + 固定 5s 兜底）

- 影响：segment 语义粒度不均（部分 scene 级、部分固定 5s）
- 处理：Phase 2 认知语义化时按 segment 重新标注，不回溯修改现有 segment

---

## 四、数据一致性（Phase 1 验收数字）

| 指标 | 值 | 目标 |
|---|---|---|
| assets | 22465 | - |
| media_files | 28096 | - |
| segments | 41814 | - |
| orphan assets | **0** | 0 ✅ |
| orphan segments | **0** | 0 ✅ |
| invalid time ranges | **0** | 0 ✅ |
| duplicate exact segments | **0** | 0 ✅ |
| Canonical 追溯（抽样 2000） | **100%** | 100% ✅ |
| assets→path 全量 | **100%** (22465/22465) | 100% ✅ |

---

*异常仅标记不删除，符合 Phase 1 指令 6。*
