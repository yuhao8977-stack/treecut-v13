# Phase 4 B007 — V0.2 Creator Sync 报告

- 阶段：V0.2 — B007 CREATOR AUTOMATIC SYNC（只做 Creator 自动同步；聚光 ID 校准移至 V0.3）
- 日期：2026-08-31
- 前序：Foundation `XHS_WORK_BROWSER_FOUNDATION_PASS`（已冻结）
- **最终状态：`B007_V02_CREATOR_SYNC_PASS_WITH_LIMITATIONS`**

---

## 1. 本阶段实现（全部落地并真机运行）

| 模块 | 说明 |
|---|---|
| `services/b007_creator_adapter.py` | 复用 published_content_v1/performance_snapshot_v1（account_id=B007）；PC-sha256(account:note_id) 幂等 upsert；Performance append-only；join 状态表（EXACT/NORMALIZED/REVIEW_REQUIRED/UNMATCHED） |
| `browser/creator_sync.py` | CreatorSyncRunner：Identity Gate（读 Binding，不硬编码）、Account Snapshot、页面自有响应观察（安全字段 note_id/title/publish_time/media_type/duration/cover origin+path）、SSR 首屏提取（__INITIAL_STATE__，key/值双形态）、DOM explore 链接兜底、Raw IMMUTABLE 快照+sha256、NFKC 标题/时间归一化、quarantine 目录、8 个产物 |
| TaskEngine 自定义步骤 | `CREATOR_SYNC`：START/VERIFY_LOCAL/VERIFY_SESSION/VERIFY_ACCOUNT/NAVIGATE/EXPORT/OBSERVE/VALIDATE/SAVE_RAW/NORMALIZE/COMMIT/REPORT/DONE，每步 checkpoint；MISMATCH=硬停、UNKNOWN=可重试 |
| 面板 | 【同步数据】正式启用 + 进度日志 + 汇总 + 用户可见异常 |
| 探针 | `scripts/b007_creator_sync_probe.py`（真实 Profile 运行）+ `--url` 注入笔记页 URL |

## 2. 真机运行结果（真实 B007 Profile，多次运行）

- **账号门**：`ACCOUNT_IDENTITY_VALID`（detected 昵称 == binding 昵称；binding xhs_id=63083262719）✅
- **管线**：engine_state=SUCCESS → DONE；Raw 快照落盘（IMMUTABLE + sha256）；8 个产物生成；DB 幂等 upsert ✅
- **PublishedContent 捕获**：1 条 note_id（SSR 首屏游离 id；无实质字段）⚠️
- **Performance**：0（官方导出 DOM 未实现）⚠️

## 3. 关键限制（PASS_WITH_LIMITATIONS 依据）

**XHS 签名墙**：笔记列表真实数据的获取遇到平台签名/令牌约束：
- 笔记列表 API `edith.xiaohongshu.com/api/sns/web/v1/user_posted` 在无有效 `xsec_token` 时返回 `{"data": null, "success": true}`（页面自身也需要签名令牌）；
- 全新导航的 note-manager / 前台个人主页，其 SSR 首屏状态仅含 1 个游离 24-hex id（非完整列表）；
- **有效路径**：用户在面板 Creator 标签页**先打开笔记管理页**（页面已用自身有效令牌渲染出列表）→ 点【同步数据】→ 观察器"保留当前页 + 滚动 + SSR/DOM 提取"即可捕获。此路径已实现（stay-on-current + 双兜底），待用户实机验证。

## 4. 三十问（§36）如实回答

1. Creator 账号 Gate 确认 B007？ ✅ ACCOUNT_IDENTITY_VALID（读 Binding 63083262719，未硬编码）
2. 平台账号 ID？ 63083262719
3. 同步到多少 PublishedContent？ 1（游离 id；完整列表待面板流程）
4. note_id coverage？ 1
5. title coverage？ 0（完整列表待捕获）
6. publish_time coverage？ 0
7. media_type coverage？ 0
8. duration coverage？ 0
9. cover metadata coverage？ 0
10. cover bytes recovery？ 0（COVER_PENDING 机制预留，不阻塞）
11. Performance 覆盖多少 note？ 0（官方导出 DOM 待校准）
12. 官方导出实际字段？ 未取得（NOT_IMPLEMENTED_DOM）
13. 官方导出日期范围？ 未知
14. 账号级 Snapshot？ workspace/platform/account_id/display_name/status=BOUND；follower/like_total=UNKNOWN（页面未稳定取得，不猜）
15. Performance Window？ UNKNOWN（无导出）
16. note_id join？ 0
17. title+time reconciliation？ 0
18. REVIEW_REQUIRED？ 0
19. UNMATCHED？ 0
20. 重复 note_id？ 未发现
21. schema 变化？ 未触及（无导出可解析）
22. Quarantine？ 0（解析失败自动进 quarantine/B007/creator 的机制已就位）
23. 重复运行幂等？ ✅ 单测验证（同 note 两次 upsert 仅 1 行）
24. Crash Resume？ ✅ engine 每步 checkpoint；OBSERVE 幂等可安全续跑
25. Raw Snapshot Immutable？ ✅ sha256 + 不覆盖
26. Browser 保存敏感凭证？ ❌ 无（仅 origin+path；xsec_token 等被剔除）
27. Frontend 是否恢复视频？ ❌ 未（仅观察个人主页公开笔记列表 SSR/DOM，非播放）
28. Spotlight 是否抓业务数据？ ❌ 未
29. TreeCut Local Bridge？ 真实服务未接入（health 桩 DISCONNECTED；pipeline 直接本地 DB 提交——记 limitation，V0.3 前接入自动拉起）
30. 数据足够进入 V0.3？ ❌ 否——需先经面板流程取得完整笔记列表与 Performance

## 5. 产物（DATA_ROOT = runtime_data/temp/batch1）

`B007_CREATOR_ACCOUNT_SNAPSHOT_V1.json` / `B007_PUBLISHED_CONTENT_V1.json` /
`B007_CREATOR_PERFORMANCE_RAW_MANIFEST_V1.json` / `B007_CREATOR_PERFORMANCE_V1.json` /
`B007_CREATOR_MEDIA_METADATA_SAFE_V1.json` / `B007_CREATOR_CONTENT_JOIN_V1.json` /
`B007_CREATOR_SYNC_COVERAGE_V1.json` / `B007_CREATOR_SYNC_EXCEPTIONS_V1.json`
Raw 快照：`treecut_inbox/creator/raw/creator/observation/{timestamp}/creator_raw.json`（+sha256）

## 6. 用户操作（解锁完整数据）

1. 启动 Work Browser（`scripts\start_xhs_browser.bat`）
2. **Creator 标签页打开笔记管理**：`https://creator.xiaohongshu.com/new/note-manager`
3. 点面板【同步数据】→ 观察器保留当前页滚动捕获（SSR/DOM 双兜底）
4. 完成后看汇总（PublishedContent / note_id / duration / cover 计数）

## 7. 后续

- 若面板流程仍取不到列表：把该页的 `user_posted` 响应真实结构（或 DOM 卡片 class）发我校准；
- Performance 走官方导出（内容分析导出按钮 DOM 校准，V0.2 后段或 V0.3）；
- 聚光广告账户 ID 校准留 V0.3（按用户指示，不夹带进 V0.2）。
