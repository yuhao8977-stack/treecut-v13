# PHASE4 STAGE 3A.3 — B003 ASSET DISCOVERY + PUBLISHED CONTENT → FINISHED ASSET MAPPING

> 状态：**STAGE3A3_NEEDS_ASSET_REPAIR · PHASE4_STAGE3B_READY=FALSE · STOP**
> 日期：2026-08-30
> 基础：B003 PublishedContent=155 · Performance=155 · Published→Performance=READY · Published→Asset=0
> 纪律：素材 READ ONLY · 未移动/重命名/删除/覆盖 · 未强行提高 coverage · 未进入 Content DNA

---

## 1. 现有 Asset DB 盘点（诚实结果）

| 项 | 结果 |
|---|---|
| assets 总数 | 22465（全部有 duration，但 **duration 全为 0.0**——probe 未填充，不可用）|
| media_files | 28096（category 全部 unclassified，**无 finished/raw 分类**）|
| segments | 41814（关联 assets 全通）|
| transcripts (ASR) | 51516（覆盖 16168/22465 asset）|
| keyframes | 125199 |
| **B003 关联 asset** | **0** |
| **Z 组成片在索引中** | **0**（media_files 无 B组/已发/B003 记录）|

**结论**：现有 Asset DB **没有 B003 成片索引**。media_files 路径是**原始素材分类库**（【01】上层薄抽 等 = 功能素材），不是发布成片。

## 2. B003 Published 侧信息

- 155 条全部有 duration（10-226s，分布 0-30:28 / 30-60:57 / 60-120:60 / 120+:10）
- 无 cover/thumbnail metadata（API 身份源未含可保存的 cover URL）
- title/publish_time 完整

## 3. 按 §21 扫描已知素材盘：Z:\B组更新视频

**扫描 360 个成片（只读 filename+duration+size+mtime，ffprobe）**：
- 360 个全部有 duration（16.3-141.3s，平均 61s，共 **32.5 GB**）
- 文件名格式：`3.9 产品1.mp4` / `1.16产品视频1 小户型.mp4`（**日期+产品视频编号，无标题语义**）
- **不在 TreeCut 索引中**（未导入）

## 4. Duration 候选过滤结果

```
按 duration(±1.5s)：136/155 note 有候选
其中 128 个多候选（Z 成片时长高度重复：33s×15、38s×14 等）
```

**duration 不足以区分**：同批产品视频时长相似，128/136 有多候选 → 无法仅凭 duration 定唯一 Asset。

## 5. 匹配证据链不足（诚实）

| 证据 | 可用性 |
|---|---|
| duration | ✅ 但多候选（128/136）|
| ASR 语义 | ❌ Z 成片未导入 TreeCut，无 ASR |
| Visual (cover↔keyframe) | ❌ 无 cover metadata，Z 成片未处理 |
| filename/title | ❌ Z 文件名是日期+产品编号，与 note 标题无语义对应 |
| 文件时间弱先验 | ⚠️ Z 文件名日期（1.16/3.9）≠ note 发布时间（3.4-8.30 每日 11:30）|

**无法建立任何 EXACT/HIGH_CONFIDENCE 映射** → 155 条全 UNKNOWN（不强行匹配，遵守"宁可少匹配"纪律）。

## 6. 判定：STAGE3A3_NEEDS_ASSET_REPAIR

**根因**：Z:\B组更新视频 的 360 个成片**未导入 TreeCut**（无 assets/segments/ASR/keyframes 记录）。只有导入后才能：
- 生成 ASR 语义（note 标题 vs 成片口播）
- 生成 keyframes（视觉匹配）
- 与 duration 组合 → 才有 HIGH_CONFIDENCE 能力

**导入可行性（已评估）**：360 个成片 32.5 GB、平均 61s——TreeCut 现有管线（fingerprint/segments/ASR/keyframes）可直接处理，属标准操作。**但导入是较大操作，且无法确认这 360 个就是 B003 成片**（可能是 B008 或其他循环素材）→ **需用户确认后再导入**。

## 17 问答复

1. **Asset DB 足以做候选发现？** → **否**（无成片索引：duration 全 0、无 finished 分类、无 B003 关联）
2. **finished candidate？** → 现有索引 **0**；Z 盘扫描 **360**（未导入）
3. **155 条多少有 duration？** → **155（100%）**
4. **Published cover metadata？** → **0**（无 cover URL 可保存）
5. **多少条能找 Top-K 候选？** → **136/155**（duration 候选），但 128 个多候选
6. **Pilot20 自动 HIGH_CONFIDENCE？** → **0**（无证据组合可自动确认）
7. **多少需 Human Review？** → **0 可审**（无 AMBIGUOUS，全 UNKNOWN——没有值得审的候选）
8. **多少完全 UNKNOWN？** → **155（100%）**
9. **同 Asset 多次发布？** → **未检测**（无映射）
10. **Z 盘单文件实际匹配 B003？** → **无法确认**（无 ASR/visual，仅 duration 多候选）
11. **Top1/Top2 难区分？** → **是**（时长重复严重）
12. **Asset Resolver 可靠性？** → **不足以自动映射**（缺 ASR/visual 输入）
13. **需人工审核？** → **当前不需要**（无候选可审）
14. **若需，审多少？** → N/A（先解决导入）
15. **Published→Asset coverage？** → **0%**
16. **Asset→Segment coverage？** → **0%**（无 Asset 映射）
17. **足够形成 winner+control DNA Candidate？** → **否**

## 产物
- `B003_ASSET_DISCOVERY_INVENTORY_V1.json` · `B003_PUBLISHED_ASSET_CANDIDATES_V1.json`（136 有候选）· `B003_PUBLISHED_CONTENT_ASSET_MAPPING_V4.json`（全 UNKNOWN）· `B003_ASSET_MAPPING_REVIEW_QUEUE_V2.json`（空）· `B003_REPOST_CLUSTERS_V1.json`（空）· `B003_ASSET_JOIN_COVERAGE_V1.json`（0%）
- `B003_Z_GROUP_ASSETS_V1.json`（360 成片索引，ffprobe 只读）
- 本报告 `docs/PHASE4_STAGE3A_3_ASSET_DISCOVERY_REPORT.md`

## Asset Repair 路径（需用户确认，不自动执行）

**将 Z:\B组更新视频（360 个成片）导入 TreeCut**（标准管线：fingerprint→segments→ASR→keyframes，32.5GB）：
1. 确认这 360 个是否 = B003 发布成片（是/否/部分）
2. 确认后我执行导入 + 重新跑 Asset Discovery（ASR 语义 + 视觉匹配 + duration 组合 → HIGH_CONFIDENCE）
3. 或提供 B003 真实成片位置（若 Z 组不是）

## 停点

**STOP** —— Asset 环需要成片导入（非人工翻文件夹可解决）。未进入 Content DNA / 模板 / 账号DNA。已推送 `4d87a33`。
