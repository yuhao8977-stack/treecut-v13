# PHASE4 STAGE 3A.2 — B003 DATA IMPORT + PUBLISHED CONTENT → PERFORMANCE JOIN

> 状态：**B003 数据导入完成（155 条 PublishedContent + 155 PerformanceSnapshot）· Asset 匹配待人工确认 · STOP**
> 日期：2026-08-30
> 前提：B003 身份已确认（BARBERRY坤宝岛台定制）· 用户提供《笔记列表明细表.xlsx》+《note_id身份表》
> 纪律：未改原始文件 · 空值不补 0 · added-WeChat=UNATTRIBUTABLE · 未进入 Content DNA

---

## 1. 数据导入成功 ✅

| 项 | 结果 |
|---|---|
| 性能表作品 | 156 条 |
| note_id 身份表 | 157 条 |
| **成功匹配** | **155 条（99.36%）**——与架构监工对账完全一致 |
| 未匹配 | 1 条：《已崩溃，伸缩岛台翻车......》（2026-04-14 11:30，观看 8）→ **UNMATCHED_DETAIL / REVIEW_REQUIRED**（API 已发布列表无此条，可能删除/隐藏/状态变化）|

**匹配方法**：标题 NFKC 规范化 + 发布时间匹配（同分钟 / ±3 分钟秒差 / ±12 小时 AM-PM 时区偏移）——发现 5 条存在 12 小时时区偏移（性能表 21:53 vs 身份表 09:53 等），已正确归并。

## 2. DB 写入（B003ManualImportAdapterV1）✅

```
published_content_v1:  155 条（account_id=B003，唯一 note_id=155）
performance_snapshot_v1: 155 条（全部有 views）
```

- 每条含：note_id / title / publish_time / duration / identity_confidence=HIGH
- 表现：views / likes / favorites / comments / shares / exposure / follower_delta
- **window=UNKNOWN**（后台累计值，窗口不可证明，禁止推测）
- **metric_type=MIXED**（未拆 Organic/Paid，不作 Pure Organic 解释）
- **added_wechat=UNATTRIBUTABLE_CENTRALIZED_B007**（未落库，纪律保持）

## 3. 数据质量（性能分布粗览）

- 155 条 note 覆盖 2026-03-04 ~ 2026-08-30（近半年）
- 每日固定 11:30 左右发布（排期规律）
- 单日 1 条 note（除少数几日 2 条）——发布密度稳定

## 4. Asset 匹配检查：Z 盘成片 **不对应** ⚠️

**`Z:\B组更新视频`（138 个成片）与 B003 的 155 条 note 无法匹配**：
- 成片日期：仅覆盖 11 天（3.9-3.27，每日 5-12 个）
- note 发布：覆盖 155 天（3.4-8.30，每日 1 条）
- 数量（138 vs 155）、日期分布、标题均不对应 → **Z 盘成片不是 B003 的发布成片**（可能是另一批循环素材或 B008 相关）

**结论**：**155 条 note 的本地成片 Asset 尚未找到**。需要用户提供 B003 实际发布的成片文件夹（或 note→成片映射表）。

## 5. 当前 Join 状态

| 链路 | 状态 |
|---|---|
| Published Content | ✅ 155 条（note_id 可靠）|
| → Performance | ✅ 155 条（views/likes/etc）|
| → Asset | ❌ 0（Z 盘不对应，待用户提供）|
| → Segment | ❌ 0 |
| → Business Cognition V2.1 | ❌ 0 |

**JOIN_COVERAGE：PERFORMANCE_JOIN_PASSED（155/155）；ASSET_JOIN_PENDING**

## 6. 下一步（需要你提供）

**B003 实际发布成片的文件夹路径**（或 note→成片映射）。已知线索：
- 如果你知道那批成片在哪（如 D:\坤宝岛台\输出 或某剪辑导出目录），告诉我路径
- 或提供 note 标题/发布时间 → 视频文件的对应关系（哪怕部分）

**Asset 对上后**：Asset → Segments → Business Cognition V2.1 → Content DNA Candidate Set 链路即可启动。

## 7. 那 1 条未匹配（不阻塞）

《已崩溃，伸缩岛台翻车......》（观看 8，4-14）API 已发布列表无 → 标 UNMATCHED_DETAIL/REVIEW_REQUIRED，不阻塞整体。

## 产物
- `B003_IMPORTED_SOURCE_MANIFEST_V1.json` · `B003_PUBLISHED_CONTENT_INVENTORY_V3.json` · `B003_PERFORMANCE_SNAPSHOTS_V3.json` · `B003_JOIN_COVERAGE_REPORT_V3.json`
- DB：`published_content_v1`（155）· `performance_snapshot_v1`（155）
- 本报告 `docs/PHASE4_STAGE3A_2_B003_IMPORT_JOIN_REPORT.md`

## 停点

**STOP** —— 数据链已完成 2/5 环（PublishedContent→Performance）。Asset 环待用户提供成片位置。未进入 Content DNA / 模板 / 账号DNA。
