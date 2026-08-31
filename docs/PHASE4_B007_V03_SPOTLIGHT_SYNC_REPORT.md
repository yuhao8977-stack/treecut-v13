# PHASE 4 — B007 V0.3 Spotlight Sync 报告

- 日期: 2026-08-31 18:52:16
- 状态: **B007_V03_SPOTLIGHT_SYNC_PASS_WITH_LIMITATIONS**

## 1. 账户（§6/§7 门 + ID 校准）

| 项 | 值 |
|---|---|
| 账户名 | T-KUBON坤宝高端岛台工厂-zx |
| account_id | 62ea6099000000001f004e37（**CANONICAL_ANCHOR_UPGRADED**：leona/user/info 页面自有响应 userId）|
| seller_id | (空) |
| ID 来源 | PAGE_OWNED_RESPONSE（非硬编码，binding 已升级）|

## 2. 捕获结果（页面自有响应，非模拟 API）

| 实体 | 数量 | 来源端点 |
|---|---|---|
| 计划 Campaign | **48** | light/campaign/data/list（20/页 ×3 页，Playwright 真实点击翻页）|
| 单元 Unit | **48** | leona/rtb/unit/search（20/页 ×3 页）|
| Creative | SOURCE_NOT_PROVIDED | /aurora/ad/manage/creative 404；最细稳定粒度=单元 |
| 推广笔记 unique | **2322** | unit.noteIds 直连 |
| 笔记关联 note_links | 4625 | 单元×笔记（多对多，1 笔记可多单元投放）|
| Paid Snapshot | 97 | ACCOUNT 1 / CAMPAIGN 48 / UNIT 48 |

## 3. 指标覆盖（今日默认范围 2026-08-31）

| 指标 | 计划级(48) | 单元级(48) |
|---|---|---|
| fee | 48 | 48 |
| impression | 28 | 48 |
| click | 28 | 48 |
| ctr | 28 | 48 |
| cpm | 28 | 48 |
| messageConsult | 28 | 48 |
| msgLeadsNum | 28 | 48 |
| msgLeadsCost | 28 | 48 |

账户级（今日）：fee=None impression=None click=None ctr=None msgLeadsCost=None

## 4. Published Join（§15/§37）

- unique promoted notes: **2322** / 2851 ACTIVE universe
- ACTIVE_PUBLISHED_MATCH: 2322（唯一笔记）
- LEGACY_IDENTITY_MATCH: 0
- UNMATCHED_PAID_NOTE: 0
- 459 legacy 未混入 ACTIVE；note_id 直连，无 title 兜底（§14）

## 5. 归因纪律（§19/§20/§36）

- PLATFORM_ATTRIBUTED: fee/impression/click/ctr/cpm/messageConsult/msgLeadsNum/msgLeadsCost 等（平台字段原样）
- UNATTRIBUTABLE_CENTRALIZED_B007: 公司总表 added_wechat 集中归 B007，**不拆给 note/creative/campaign**
- SOURCE_NOT_PROVIDED: creative 级 / 账号 7d/30d
- Creator 2840 Performance snapshots 未修改（§22）

## 6. 存储（§30/§31）

- C free: 启动前 72.5GB（WARNING_BUT_OPERATIONAL，结构化同步允许，无媒体下载）
- Raw：E 盘 treecut_inbox/creator/raw/creator/spotlight_*（IMMUTABLE + sha256）
- 无大型导出（今日视图数据量小）

## 7. Limitations

- AVAILABLE_PAID_DATE_RANGE：仅今日默认视图；自定义/全历史范围待扩展（分批 snapshot）
- Creative 粒度：SOURCE_NOT_PROVIDED（单元为最细稳定粒度）
- 账号 7d/30d：SOURCE_NOT_PROVIDED

## 8. V0.4 Readiness（§39）

- 48 计划 + 48 单元 + 2322 推广笔记 + 97 快照 + 全 ACTIVE join → **数据足以进入 V0.4 Creator+Spotlight Dual-source Join**
- 但日期范围建议在 V0.4 前扩展（多窗口 snapshot）以获得跨时间投放历史

## 9. 下一步（STOP — 不自动进入 V0.4）

等待架构师确认；Winner/Sample/视频恢复/Content DNA 均在 Prohibitions。
