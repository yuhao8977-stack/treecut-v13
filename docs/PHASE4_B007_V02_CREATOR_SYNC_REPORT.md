# PHASE 4 — B007 V0.2 Creator Sync 最终报告

- 日期: 2026-08-31 16:57:49
- 状态: **B007_V02_CREATOR_SYNC_PASS_WITH_LIMITATIONS**

## 1. 结果摘要

| 指标 | 值 |
|---|---|
| Published unique notes (已发布列表穷尽) | **3310**（含 459 条历史遗留 id-only 行）|
| 已发布 Tab 捕获 | **2851**（pages 0..285，288 轮滚动后连续 3 轮无新增 → PUBLISHED_LIST_EXHAUSTED=TRUE）|
| 页面 ALL 计数 | 2851（与捕获一致，无需再以 ALL=2851 为目标）|
| title coverage | 2854 / 3310 (86.2%) |
| publish_time coverage | 2851 (86.1%) |
| content_type coverage | 2897 (87.5%) |
| duration coverage | 2843 (85.9%) |
| cover metadata coverage | 2851 (86.1%) |
| Performance rows | 2840（source=SRC-B007-POSTED-OBSERVED）|
| Join | {"EXACT_NOTE_ID_MATCH": 2840}（legacy id-only 未 join: 470）|
| DB integrity | ok |
| C free before → after | 74.1 → 72.9 GB |

## 2. Response Schema Map（回答「为何 Rich Coverage 低」）

471 条中仅 16 title / 12 duration+cover，根因是批量捕获走的是 CLASS_B 路径，CLASS_A（posted 富响应）只在 16 次观察中命中 1 次（page=0 仅 12 条）。

证据：
- - 观察历史 16 个 creator_raw.json：仅 run 20260831_140940 捕获到 posted 端点（12 条全富字段）；其余 run 的 observed_notes 来自 DOM/SSR（id-only）\n- posted 分页此前未打通：旧代码只点击「下一页」按钮（UI 无此控件）+ 窗口滚动（实际是 .content 容器滚动），因此只拿到 page=0 的 12 条\n- DB source_refs 分布佐证：409+50 行仅 OBSERVATION(a8ae/ee6d)，11+1 行含 b36e8df41e58（posted）\n

修复：容器滚动分页打通后，posted 响应（CLASS_A）覆盖率达：
- title/time/media_type/cover = 100%，duration = 99.7%（2851 records / 285 页）

三类响应：
- CLASS_A posted 富响应（id/title/time/type/duration/cover/engagement）
- CLASS_B DOM/SSR id-only（历史 471 的来源）
- CLASS_C 详情端点 schema 未捕获 → UNKNOWN（Detail enrichment FALLBACK ONLY，未逐条调用）

## 3. Enrichment

- 新入库 0，更新 0，真实冲突 0（13 条 duration int/float 表示差异 → 非冲突）
- cover metadata 落库 0 条（cover_url_safe/cover_origin/cover_path，非阻塞，无字节下载）
- 字段来源：POSTED_CAPTURE:<run>，precedence = POSTED_CAPTURE > 旧 OBSERVATION(DOM/SSR)
- 凭证纪律：xsec_token/xsec_source/signed URL 未落库

## 4. Performance

- 来源：Route B 页面自有响应（posted 响应的 view_count/likes/comments_count/shared_count/collected_count）
- 行数：2840；window=UNKNOWN（累计值）；snapshot_time=2026-08-31 16:52
- 官方导出：**EXPORT_LOCATOR_UNKNOWN**（attempts: note-manager 语义文本扫描 / /data/* 404 / 数据看板无导出按钮）→ limitation
- 账号级 7d/30d：SOURCE_NOT_PROVIDED（不分配给笔记）

## 5. Join

- 方法：note_id（primary）；未用 title+time 兜底（无需）
- 状态分布：{"EXACT_NOTE_ID_MATCH": 2840}
- 459 条历史 id-only 行不在已发布列表（可能已删除/私密）→ 保留为历史证据，未 join

## 6. 存储纪律

- C free 74.1 → 72.9 GB（WARNING 区间，无大型媒体下载）
- Raw Snapshot / 证据：E 盘 treecut_inbox（IMMUTABLE + sha256）
- 大型媒体未触碰；cover 仅存 URL 元数据
- B003 数据未动（155 published / 155 perf rows）

## 7. Limitations

- 官方导出按钮定位未知（EXPORT_LOCATOR_UNKNOWN）；Performance 采用页面自有响应 Route B\n- 账号级 7d/30d 指标未捕获（SOURCE_NOT_PROVIDED）\n

## 8. 下一步（STOP — 不自动进入 V0.3）

- 等待架构师确认后再继续；V0.3 Spotlight Sync / Sample Selection / 视频恢复等均在 Prohibitions 列表。
