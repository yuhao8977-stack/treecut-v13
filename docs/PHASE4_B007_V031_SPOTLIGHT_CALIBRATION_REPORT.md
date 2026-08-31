# PHASE 4 — B007 V0.3.1 Spotlight 校准报告（时间范围 + 最低粒度）

- 日期: 2026-08-31 19:37:29
- 状态: **B007_V031_SPOTLIGHT_CALIBRATION_PASS_WITH_LIMITATIONS**

## 1. 关键结论

1. **可选最早日期**: SOURCE_NOT_PROVIDED（未遍历日历全部月份；平台最早投放 ~2026-04，见 campaigngroup createTime）
2. **可选最晚日期**: 2026-08-31（今日）
3. **最大单次查询跨度（preset）**: 30 天（presets: 昨天/最近7天/最近14天/最近30天）；自定义上限 UNKNOWN
4. **Preset**: 昨天 / 最近7天 / 最近14天 / 最近30天（无 今日/90天/LIFETIME preset）
5. **指标随窗口变化**: 是（30d fee ≥ 7d fee 占比 85.7%，63 条双窗口同笔记样本）
6. **fee 等字段窗口语义**: **SELECTED_DATE_RANGE**（非 LIFETIME）
7. **历史回填窗口**: LAST_7D / LAST_14D / LAST_30D（bounded，无逐日抓取）
8. **Campaign start/end**: startTime + expireTime + campaignCreateTime（48/48 计划有 createTime）
9. **Unit start/end**: startTime + expireTime + unitCreateTime（48/48）
10. **真实 Creative 层**: 未发现（/aurora/ad/manage/creative 404；创意载体=单元）
11. **真实 Note 层 Paid Metrics**: **存在**（leona/rtb/common/data/report 笔记报表：noteId + fee/impression/click/messageConsult/msgLeadsNum/msgLeadsCost）
12. **最终最低粒度**: **PAID_METRIC_LOWEST_GRAIN = NOTE**
13. **Unit 级快照数**: 132（{"LAST_14D": 28, "LAST_30D": 28, "LAST_7D": 28, "REPORT_RANGE": 48}）
14. **Creative 级快照数**: 0（SOURCE_NOT_PROVIDED）
15. **Note 级快照数**: 501（{"LAST_14D": 170, "LAST_30D": 167, "LAST_7D": 164}）
16. **是否发生指标向 Note 分摊**: **NO**（Unit 指标不拆；note 级指标为平台笔记报表独立 source）
17. **ASSOCIATION_JOIN_READY**: **TRUE**（Creator note ↔ Paid association，4625 links）
18. **NOTE_PAID_METRIC_JOIN_READY**: **TRUE**（Creator note ↔ note 级 paid metric，501 snapshots + 可扩展）
19. **足够进入 V0.4**: **是**（结果 A：双源完整 Join 可执行）
20. **V0.4 必须遵守**: note 级指标来自笔记报表（PLATFORM_ATTRIBUTED）；Unit 级指标仅作 Unit 效率分析；
    creative 级缺失；公司加微仍不参与；时间窗口语义=SELECTED_DATE_RANGE

## 2. 发现记录

- 日期选择器：`d-daterangepicker`（报告页/计划页通用），preset 按钮语义文本可点，30d 设置实测生效
- **笔记级投放指标**：数据板块 → 笔记报表（datareports-basic/note）→ leona/rtb/common/data/report 返回
  noteId + 全指标 + noteCreateTime/noteTitle —— V0.3 的 Unit 粒度限制**已解除**
- 窗口回填：3 个 preset 窗口 ×（笔记报表 + 计划 + 单元）证据落 E（IMMUTABLE + sha256）
- 生命周期：campaignCreateTime 48/48、unitCreateTime 48/48、noteCreateTime 已随报表入库

## 3. Limitations

- 笔记报表分页只捕获到 ~10 页/窗口（~165 笔记）；611 行(7d)全量回填待后续扩充分页捕获
- 90 天 / LIFETIME 无 preset → 更长历史需自定义按月分块
- Creative 层不存在（平台以单元为创意载体）

## 4. 下一步（STOP — 不自动进入 V0.4）

V0.4 可执行完整双源 Join（ASSOCIATION + NOTE_PAID_METRIC 均 READY）；
等待架构师确认后再进入。
