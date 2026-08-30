# PHASE4 STAGE 3A.1 — B003 ACCOUNT IDENTITY REPAIR + DATA RECOVERY REPORT

> 状态：**STAGE3A_WAITING_FOR_B003_IMPORT · PHASE4_STAGE3B_READY=FALSE · STOP**
> 日期：2026-08-30
> 前置：STAGE3A_NEEDS_DATA_REPAIR（B003 身份未注册）
> 纪律：未改用 B008 替代 · 未强并"坤宝研究设计院" · 未虚构数据 · 未进 Content DNA · added-WeChat 纪律保持

---

## 1. B003 身份正式注册 ✅

`ACCOUNT_IDENTITY_REGISTRY_V1.json`：
- **account_internal_id = B003 · display_name = BARBERRY坤宝岛台定制 · platform = XIAOHONGSHU · confidence = HUMAN_CONFIRMED · status = ACTIVE**
- aliases：BARBERRY坤宝岛台定制 / 坤宝岛台定制 / BARBERRY
- 同时注册：B008 = KUBON坤宝岛台工厂（FUTURE_SECONDARY_PILOT_CANDIDATE，INDEPENDENT）、坤宝研究设计院（UNVERIFIED/PENDING_IDENTITY_CHECK）

## 2. 为什么之前搜不到 B003 ✅

之前只搜字符串 "B003"，但旧数据没有写内部代号。本次改用**显示名（BARBERRY/坤宝岛台定制）+ 4 个标题锚点**重新全盘搜索（DB/DATA_ROOT/repo/Desktop/Downloads/E盘/D盘/表格内容级），**发现 2 条真实 B003 线索**。

## 3. 通过 display name / title anchors 新发现 ✅

| 发现 | 来源 | 详情 |
|---|---|---|
| **1 条可靠 note** | `拆解爆款视频0.1.xlsx` | note `654215c90000000023039459`，标题"岛台vs传统餐桌🏠该如何选择呢🧐"，文案含 **@BARBERRY坤宝**，点赞 4235/收藏 2838/评论 62 |
| 1 条锚点风格标题 | 同上 | "再见了传统横厅👋👋（沙发后放个岛台简直不要太香🔥）"匹配锚点"大横厅设计布局 沙发后岛台"，但**无 note_id**（不视为可靠身份）|
| **D:\坤宝岛台 运营系统** | 新发现 | 坤宝岛台小红书自动运营系统（PublishRecord/AnalyticsEngine/每周复盘），有素材库/热词/封面库 210 条，但**无生产发布记录/数据统计** |

## 4. "坤宝研究设计院"29 条 = NOT_B003 ✅

Identity Comparison（display_name / note_id / 标题锚点）：显示名不含 BARBERRY/坤宝岛台定制、不含 B003 已知 note、无锚点标题重叠 → **NOT_B003**。**保持独立账号，不强并**。

## 5. B008 保持独立 ✅

B008 = KUBON坤宝岛台工厂 → FUTURE_SECONDARY_PILOT_CANDIDATE（本轮不进入 Content DNA，不替代 B003）。

## 6-7. 数据恢复 + Added-WeChat 纪律 ✅

恢复优先级已定义（Published Note → Performance → Acquisition → Paid → Asset）。**added-WeChat 纪律保持**：加微信统一归 B007 公司表 → B003 的 added_wechat/cost_per_added_wechat/单视频加微全部 = **UNATTRIBUTABLE_CENTRALIZED_B007**（不阻塞 private message/lead/paid lead 分析）。

## 8-9. 导入规格 + 适配器 ✅

- `B003_REQUIRED_DATA_IMPORT_SPEC_V1.json`：**Minimum Viable Stage3A Dataset**（note_id/url/title/publish_time + views/likes/favorites/comments/shares + 可用的 private_messages/leads + paid 字段）；截图标 MANUAL_SOURCE 保留 provenance
- `src/treecut/services/b003_import_adapter.py`（B003ManualImportAdapterV1）：xlsx/csv/json → raw import → normalize → identity validation → PublishedContentRecord；不覆盖原文件
- **Smoke PASS**：同 note 多来源合并去重（note_id 为身份证据）✅ / PerformanceSnapshot append-only ✅ / published_content_id ≠ asset_id ✅ / snapshot 无 added_wechat 列（UNATTRIBUTABLE 不落库）✅

## 10-13. 去重 / Asset 查找 / Historical finished video / Mapping review

- 去重：note_id 优先，同 note 合并 source_refs + 保留多个 snapshot
- Asset 查找顺序：known mapping → exact metadata → exact hash → filename → duration/time → visual → manual；FUZZY 不直接成 Truth
- **允许 PublishedContent → Finished Asset → Segments**（Stage3 Pilot 合法路径，不要求还原原始素材）
- Mapping 分级 EXACT/HIGH_CONFIDENCE/AMBIGUOUS/UNKNOWN；AMBIGUOUS/UNKNOWN 不进 Business Cognition Join

## 14. Performance 窗口 ✅

旧 Excel 只有累计值 → performance_window=**UNKNOWN**（或 LIFETIME 仅可证明时）；禁止推测 D7/D30。拆解表 1 条 note 的表现是单值 → window=UNKNOWN、metric_type=MIXED（不可作 Organic 解释）。

## 15-18. V2 输出 + Gate

- `B003_PUBLISHED_CONTENT_INVENTORY_V2.json`：**可靠 Published Content = 1**（654215c9）
- `B003_PUBLISHED_CONTENT_ASSET_MAPPING_V2.json`：0 映射（无本地视频关联）
- `B003_PERFORMANCE_SNAPSHOTS_V2.json`：1 条（单值，window=UNKNOWN）
- `B003_JOIN_COVERAGE_REPORT_V2.json`：**Asset→Segment=0 / Business Cognition coverage=0 → JOIN_GATE_NOT_PASSED**
- 未生成 DNA Candidate Set（Join Gate 未过）

## 19-20. 最终状态

**STAGE3A_WAITING_FOR_B003_IMPORT**（架构已可用，业务数据未进系统——不是 FAIL）

---

## 20 问答复

1. **B003 注册为 BARBERRY坤宝岛台定制？** → **是**（HUMAN_CONFIRMED）
2. **为何搜不到？** → 只搜 "B003" 字符串；旧数据无内部代号；已改用显示名+锚点
3. **新发现多少？** → **1 条可靠 note（654215c9，@BARBERRY）+ 1 条锚点风格标题（无 note_id）+ D:\坤宝岛台 运营系统（无生产数据）**
4. **坤宝研究设计院 = B003？** → **NOT_B003**（display/note/锚点均不匹配）
5. **B008 独立？** → **是**（FUTURE_SECONDARY_PILOT_CANDIDATE）
6. **B003 PublishedContent？** → **1**（本地可靠）
7. **可靠 note identity？** → 1（654215c9）
8. **Performance coverage？** → 1 条（单值 window=UNKNOWN）
9. **Private message/lead？** → 0（本地无）
10. **Paid？** → 0（本地无）
11. **added-WeChat UNATTRIBUTABLE？** → **是**（UNATTRIBUTABLE_CENTRALIZED_B007）
12. **可映射 Asset？** → 0
13. **AMBIGUOUS？** → 0（1 条 note 无视频可映射，非 AMBIGUOUS）
14. **Asset→Segment？** → 0%
15. **Business Cognition？** → 0%（无资产可运行 V2.1）
16. **Join Gate？** → **未通过**（需 B003 视频资产或后台数据）
17. **需用户导入后台数据？** → **是**（小红书创作者后台导出）
18. **最小导入字段？** → note_id/url/title/publish_time + views/likes/favorites/comments/shares + 可用私信/线索 + paid（见 Import Spec）
19. **DNA Candidate Set？** → **否**（Join Gate 未过，未生成）
20. **PHASE4_STAGE3B_READY？** → **FALSE**

---

## 产物
- `ACCOUNT_IDENTITY_REGISTRY_V1.json` · `B003_KNOWN_CONTENT_ANCHORS_V1.json` · `B003_REQUIRED_DATA_IMPORT_SPEC_V1.json`
- `B003_PUBLISHED_CONTENT_INVENTORY_V2.json` · `B003_PUBLISHED_CONTENT_ASSET_MAPPING_V2.json` · `B003_PERFORMANCE_SNAPSHOTS_V2.json` · `B003_JOIN_COVERAGE_REPORT_V2.json`
- `src/treecut/services/b003_import_adapter.py`（B003ManualImportAdapterV1 + PublishedContentRecord + PerformanceSnapshot append-only）
- `scripts/stage3a1_*.py`（identity_registry/import_spec/identity_compare/adapter_smoke）
- 本报告 `docs/PHASE4_STAGE3A_1_IDENTITY_REPAIR.md`

## 停点

**STOP** —— B003 身份已修，架构（Registry/Import Adapter/Import Spec）就绪；**等小红书后台数据导入**后即可继续 Stage3A 数据链（Asset → Segment → Business Cognition → Performance Join）。未自动进入 Stage3B / 模板 / 账号DNA。已推送 `33b0d97`。
