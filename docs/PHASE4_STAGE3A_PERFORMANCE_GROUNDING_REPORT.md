# PHASE4 STAGE 3A — PUBLISHED CONTENT IDENTITY + PERFORMANCE GROUNDING + B003 PILOT

> 状态：**STAGE3A_NEEDS_DATA_REPAIR · PHASE4_STAGE3B_READY=FALSE · STOP**
> 日期：2026-08-30
> 基础：Stage2 = PASS_WITH_LIMITATIONS（commit `59a2194`）· Knowledge V1.2（`a9ac59f6…`）· Business Cognition V2.1
> 纪律：未虚构数据 · 未进入 Content DNA · 未模板挖掘 · 未账号学习 · 未自动修改知识库

---

## ⚠️ 首要结论：B003 数据在当前环境不存在

**诚实盘点结果（不假设数据存在）**：DB 全部 60+ 表、DATA_ROOT 全部文件、repo、Desktop、Downloads、E 盘 TreeCut 目录——**无任何含 "B003" 代号的数据**。

- `account_dna` 表：空（0 行）
- `sources` 表：4 行（Phase1 来源注册，非发布内容）
- `账号清单.docx`：5 个账号名（坤宝岛台颜值设计院/颜值研究设计院/高定岛台/铁牛设计师/设计师），**无 B003 代号映射**
- 唯一含 "B00x" 的文件：`【B008】【KUBON坤宝岛台工厂】爆款内容记录表.xlsx`（是 B008，不是 B003）

## 0. Stage2 正式冻结 ✅

`PHASE4_STAGE2_FINAL_FREEZE.json`：engine=V2.1、rule=STAGE2_1_GATES_V1、knowledge=V1.2（`a9ac59f6…`）、Fresh18 AI_LOCK（`818f8d61…`）、verdict=PASS_WITH_LIMITATIONS、6 条 known limitations（含 DINING=LIMITED_CONTEXT_VALIDATION）、commit=59a2194。

## 1. Consumer Policy ✅

`STAGE3_BUSINESS_COGNITION_CONSUMER_POLICY_V1.json`：
- SUPPORTED = Evidence-backed semantic feature；**DINING/DINING_CONVENIENCE = LIMITED_CONTEXT_VALIDATION**（不能作单独 Hard Performance Explanation）
- CANDIDATE = soft feature（非 Hard Truth）
- **UNKNOWN = MISSING/INSUFFICIENT MACHINE COGNITION，绝不能解释为 FALSE/NOT_PRESENT/NOT_USEFUL**
- Decision Factor/Trust Signal/Shot Function/Search Intent = CANDIDATE ONLY；Role/Theme = AFFINITY ONLY
- ConflictResolverV2 = STRUCTURALLY_VALIDATED / LIMITED_FRESH_HUMAN_EVIDENCE

## 2. B003 Pilot — 数据不可用

**无法执行 B003 Pilot**（数据不存在）。但发现 2 个候选 Published Content 源（见 §3）。

## 3-4. 数据源 Inventory + Published Content

`B003_DATA_SOURCE_INVENTORY.json`（B003=0）+ `B003_DATA_SOURCE_DISCOVERY.json`：

| 源 | 账号 | 内容数 | 表现数据 | 可用性 |
|---|---|---|---|---|
| SRC-B008-VIRAL | **B008**（KUBON坤宝岛台工厂）| 143 条含链接 | 点赞/收藏/评论/互动率/**视频互动/私信开口/DMP行为/直播推广/商品推广** | 最完整，需清洗（多级表头+DISPIMG）|
| SRC-KBYSJY-ACCOUNT | **坤宝研究设计院**（无代号）| 29 条 | 标题/类型/封面点击率/点赞/收藏/评论 | note_id 完整，无投流/私信 |
| SRC-XHS-REGISTER | 未知 | 1 行有效 | 账号级消耗/私信/加微/转化 | 账号级非 note 级，added-WeChat 集中归集 |
| SRC-GROUP-RECONCILIATION | G组 | 24 行 | 订单/对账 | 非内容数据 |

**B003_PUBLISHED_CONTENT_INVENTORY_V1.json：total=0**（诚实空）。

## 5-7. Published Content 身份 / Asset 映射

- `published_content_id` 概念已定义（发布行为 ≠ asset，因同视频可多账号/重发/改标题）
- `B003_PUBLISHED_CONTENT_ASSET_MAPPING_V1.json`：**total=0**（无 B003 内容可映射）
- 映射方法优先级已定义（EXACT_PLATFORM_ID_METADATA → … → UNKNOWN）；AMBIGUOUS 入队，不强行匹配
- **注意**：B008 的 note 链接是 `xiaohongshu.com/explore/…`，但**无视频文件关联**——Asset→Segment 映射需确认视频文件是否存在

## 8-15. Performance / 纪律定义 ✅（规则就绪，数据缺失）

- PerformanceSnapshotV1 字段定义完成（append-only，不覆盖旧快照）
- Organic/Paid 严格分离（ORGANIC/PAID/MIXED/UNKNOWN）
- **added-WeChat 纪律**：无法证明 note→具体加微信归属 → **UNATTRIBUTABLE**（不生成单视频加微数/成本）
- performance_window（D1/D3/D7/D14/D30/LIFETIME/UNKNOWN）——旧数据无法确定则 UNKNOWN
- 4 维度分离（ORGANIC_REACH/ENGAGEMENT_QUALITY/ACQUISITION_SIGNAL/PAID_EFFICIENCY），不生成万能分
- Acquisition 优先 private_messages/leads/forms/paid_leads；Added-WeChat 仅可归因时用

## 16-17. Effectiveness Evidence / 优先级

PerformanceEvidenceV1（STRONG_ACQUISITION_SIGNAL/STABLE_PAID_DELIVERY/HIGH_QUALITY_INTERACTION/HIGH_ORGANIC_REACH/LOW_INFORMATION/INSUFFICIENT_DATA）多标签并存；selection 优先级：Acquisition → Stable paid → Interaction → Pure reach（仅 selection policy，非"低播放=差"）。

## 18-19. B003 Inventory + Join Coverage Gate

- `B003_PUBLISHED_CONTENT_INVENTORY_V1.json`：B003 找到 0 条
- `B003_JOIN_COVERAGE_REPORT_V1.json`：**全部 coverage = 0.0%** → **JOIN_COVERAGE_GATE_FAILED**
- **按 §19 纪律：关键 identity 数据缺失 → STOP，禁止进入 Content DNA**

## 20-22. Business Cognition / Timeline / UNKNOWN

- V2.1 运行范围、ContentSegmentTimelineV1、cognition_coverage 定义完成（规则就绪）
- 无 B003 内容 → 未运行（不虚构）
- UNKNOWN 语义按 Consumer Policy（COGNITION_COVERAGE_LOW ≠ 没有卖点）

## 23-27. 因果语言 / Shortlist / 模板 / 账号 DNA

- 禁止因果语言（ASSOCIATED_WITH/CO_OCCURS_WITH/OBSERVED_IN，禁止"抽屉导致转化"）——定义完成
- **B003_CONTENT_DNA_CANDIDATE_SET_V1.json：EMPTY**（数据链未建立）
- 不生成 ACTIVE/WINNING TEMPLATE；B003_CONTENT_PROFILE 不产出（无数据）

## 29. 19 问答复

1. **Stage2 正式冻结？** → 是（PHASE4_STAGE2_FINAL_FREEZE.json）
2. **限制进入 Consumer Policy？** → 是（DINING=LIMITED_CONTEXT_VALIDATION 等）
3. **B003 找到多少 Published Content？** → **0**（无任何 B003 数据）
4. **多少有可靠 note identity？** → 0（B003）
5. **多少有 Performance？** → 0（B003）
6. **多少可可靠映射 Asset？** → 0（B003）
7. **多少 AMBIGUOUS？** → 0（无数据可映射）
8. **Asset→Segment coverage？** → 0%（无 B003 asset）
9. **Business Cognition coverage？** → 0%（无内容可运行）
10. **Organic/Paid 是否分开？** → 规则已定义，无数据可验证
11. **MIXED/UNKNOWN 指标？** → 无数据
12. **是否错误使用集中 added-WeChat？** → 否（已标记 UNATTRIBUTABLE 纪律，未反推）
13. **Performance Window 可追踪？** → 规则已定义（D1-D30/UNKNOWN），无数据
14. **哪些指标可靠性最高？** → 无法评估（无 B003 数据）；B008 的互动/私信列可用但未验证
15. **B003 shortlist？** → 0 条（无法生成）
16. **Shortlist 为何入选？** → N/A
17. **包含对照内容？** → N/A（无 shortlist）
18. **COGNITION_COVERAGE_LOW？** → N/A（无内容）
19. **数据 lineage 足够进入 Content DNA？** → **否（JOIN_COVERAGE_GATE_FAILED）**

**最终判定：STAGE3A_NEEDS_DATA_REPAIR**
**PHASE4_STAGE3B_READY = FALSE**

---

## 关键决策点（需用户确认）

**B003 数据不存在，但有 2 个可用替代**：

1. **确认 B003 = 哪个账号？**（账号清单 5 个候选：颜值设计院/颜值研究设计院/高定岛台/铁牛设计师/设计师）
2. **B003 数据是否需导出导入？**（小红书后台 note 导出 + 表现快照 + 投流记录）
3. **是否允许以 B008 作为 Pilot 替代？**（数据最完整：143 条 + DMP 投流行为 + 私信开口——但需先确认其视频文件存在以做 Asset→Segment 映射）
4. **"坤宝研究设计院"29 条是否 = B003？**（有完整 note_id，无投流/私信）

**在身份确认 + 数据导入前，Stage3B Content DNA 严格冻结。**

## 产物
- `PHASE4_STAGE2_FINAL_FREEZE.json` · `STAGE3_BUSINESS_COGNITION_CONSUMER_POLICY_V1.json`
- `B003_DATA_SOURCE_INVENTORY.json` · `B003_DATA_SOURCE_DISCOVERY.json`
- `B003_PUBLISHED_CONTENT_INVENTORY_V1.json` · `B003_PUBLISHED_CONTENT_ASSET_MAPPING_V1.json` · `B003_PERFORMANCE_SNAPSHOTS_V1.json` · `B003_JOIN_COVERAGE_REPORT_V1.json` · `B003_CONTENT_DNA_CANDIDATE_SET_V1.json`
- `scripts/stage3a_*.py`（freeze/policy/discovery/outputs）
- 本报告 `docs/PHASE4_STAGE3A_PERFORMANCE_GROUNDING_REPORT.md`

## 停点

**STOP** —— Stage3A 数据链未建立（B003 缺失），判定 NEEDS_DATA_REPAIR。未自动进入 Stage3B / 模板 / 账号DNA / Script Intelligence / Director / AutoCut。
