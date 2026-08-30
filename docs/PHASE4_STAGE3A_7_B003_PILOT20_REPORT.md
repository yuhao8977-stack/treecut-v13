# Phase 4 Stage 3A.7 — B003 Pilot20 Published Media Recovery（工具与就绪报告）

- 日期：2026-08-30
- 阶段：Stage 3A.7（Pilot20 已发布媒体恢复）
- 最终状态：**STAGE3A7_PILOT20_TOOLING_READY（sample_definition=CORRECTED_AND_FROZEN，等待用户浏览器执行 20 条 Formal Pilot20 恢复；TECH_PILOT1 单独统计）** — 最终裁定（PASS / PASS_WITH_LIMITATIONS / NEEDS_MEDIA_REPAIR / RECOVERY_BIAS_DETECTED）仅在浏览器恢复 + 本地验证完成后出具
- 前序：Stage 3A.6 Pilot1 EXACT PUBLISHED MEDIA 端到端 PASS（commit `c46b1b8`）

---

## 1. 范围与架构师批准（§0-55 固化）

架构师批准（Stage3A.7 约束，含 Sample Definition 修正裁定）：

- **Pilot20 = 原始冻结 20 条，全部待恢复（PILOT20_TOTAL = 20，PENDING = 20）**。
- **TECH_PILOT1（6a8d75aa000000002503e3e2）= 独立技术验证样本，不计入正式 Pilot20 统计**（第 21 条 Known Good Reference）。
- 不再研发新恢复路线；目标从"研究怎么恢复视频"切换为"**验证路线在高中低表现 20 条上稳定，形成可靠媒体样本集**"。
- **19 → 20 是 Sample Definition Correction，不是样本扩容**：未新增任何笔记；'Remaining 19' 基于 'Pilot20 = Pilot1 + 19' 的错误文字假设（Pilot1 从未属于 Frozen Pilot20），程序化核验 V1/V2/V3 历史 manifest 均不含 6a8d75aa。强行事后删 1 条凑 19 将改变预选 strata / duration / publish-time / diversity → POST_HOC_SAMPLE_SELECTION_BIAS。**Frozen Manifest Truth 优先于文字假设**。
- 禁止自动扩展到 155 条（155 库身份已建，媒体恢复不在本轮）。
- 禁止：Content DNA、Template Mining、Account DNA、Script Intelligence、Director、AutoCut。

## 2. 样本定义修正（CORRECTED_AND_FROZEN）

架构师裁定（已接受，执行记录见 `B003_PILOT20_SAMPLE_DEFINITION_CORRECTION_V1.json`）：

- **TECH_PILOT1**：1 条独立技术验证样本（note `6a8d75aa000000002503e3e2`），用途=验证 Published Playback → Exact Media → Canonical Asset → Segment → ASR → Business Cognition 技术链路。**不计入正式 Pilot20 统计样本**。
- **FORMAL PILOT20**：使用此前已冻结的**原始 20 条 manifest**，全部待恢复（PENDING_RECOVERY = 20）。**不得**因 Pilot1 成功而从原 Pilot20 删除任意 1 条。
- 整个 Stage3A 最多形成 **21 条 Exact Published Media 样本 = 1 Tech Pilot + 20 Formal Pilot20**。
- **性能分层（冻结）**：HIGH = 6，MID = 7，LOW = 7（冻结 manifest 实际结果，保持不变）；此前 "HIGH 7/MID 7/LOW 6" 描述标记 **SUPERSEDED_BY_FROZEN_MANIFEST_AUDIT**。
- **Pilot1 处置**：KNOWN_GOOD_REFERENCE / TECHNICAL_BASELINE；不得重新下载、不得重复注册、不得混入 Pilot20 恢复成功率分子/分母。
- **统计必须分开**：TECH PILOT = 1/1 Exact；FORMAL PILOT20 = X/20 Exact（+ Blocked / Invalid / Conflict + High X/6 / Mid X/7 / Low X/7）。**禁止报告 X/21 作为 Pilot20 成功率**；允许额外报告 TOTAL_RECOVERED_REFERENCE_MEDIA = Pilot1 + Formal Pilot20 Exact。
- **Content DNA 纪律**：Pilot20 正式 20 条 = stratified analytical sample；Pilot1 不得因技术恢复成功自动加入 winner/control 分析样本（须满足 Candidate Selection Policy 才可作为额外内容样本）。
- **Recovery Bias 仅针对 Formal Pilot20** 计算（performance stratum / 发布时间 / duration / codec / 媒体形式），Pilot1 不混入。

正式恢复清单：`B003_PILOT20_RECOVERY_MANIFEST_V2.json`（20 条，字段 pilot_index/note_id/title/publish_time/published_duration/performance_stratum/cover_sha256/current_status/expected_filename，不含 Pilot1）。
旧 `B003_PILOT20_REMAINING19_MANIFEST_V1.json`：**保留文件**，标 `SUPERSEDED_SAMPLE_DEFINITION_ERROR`，禁止继续消费。

## 3. 冻结的有效技术事实（Pilot1 验证）

| 事实 | 值 |
|---|---|
| 文件大小 | 7,579,070 B（Full GET 200 精确匹配） |
| 时长 | 59.977256 s（ffprobe） |
| SHA256 | `1c8bf25bc29e91b1c9e46529a460aa83f32919b7ce3dac5e1fb4bae1461a50a4` |
| 编码 | hevc / 720x1280 / 30fps / aac 44100 stereo |
| 容器 | ISO BMFF（ftyp + moov + moof/mdat；真实 mdat 7,528,125 @ offset 50945） |
| Canonical Asset | `ae35ab1981e84b1f9aa6942b937d8c90`（media_id 28252，DERIVED_FROM_PLATFORM_PUBLISHED_MEDIA） |
| Segments | 20 段 / coverage 0.921（SceneDetector） |
| Business Cognition V2.1 | STORAGE/CHARGING_POWER/POWER_CONVENIENCE/FLEXIBLE_CAPACITY = SUPPORTED(A)；STORAGE_EFFICIENCY = CANDIDATE；conflicts 0 |
| 正确入口 | Creator Note Manager → `explore/{note_id}` Published Playback Page → 播放 → 观察实际媒体 |

## 4. 永久废弃路线（不得复活）

1. 随机 blob 拾取（V1 部分 404KB blob → 无 ftyp/moov/mdat，ffprobe "moov atom not found"）— 废弃。
2. Range 206 → FIRST_RANGE_FAILED 语义缺陷（206 对 Range 是成功）— V2_RANGE_LOGIC_DEFECT_CONFIRMED，废弃。
3. 浏览器 mdat 字符串扫描作为最终判据 — V3 CONTAINER_GATE_FAILED 假阴性确认（真实 mdat 存在但 JS 扫描 FALSE），容器真相只信 ffprobe，废弃。
4. note-detail（statistics/note-detail）作为视频入口 — 无真实视频资源（BLOCKED/resources=0），废弃。

## 5. 本轮工具

- 文件：`tools/B003_PILOT20_RECOVER_CURRENT_NOTE_V1.js`（通用、跨页面复用，20 条待恢复 note_id 内嵌）
- 函数：`__B003Pilot20RecoverCurrent()`
- **当前页身份门**：从 `window.location.pathname` 读 `/explore/{note_id}`，必须命中清单，否则 NOT_IN_PILOT20（不保存 location.search / xsec_token / cookie / auth / signed query）。
- **媒体资源选择**：video element currentSrc + 页面自有 fetch/XHR 观察（绝不独立 fetch，防 406），非最大 blob。
- **保存门**：Full GET（无 Range），期望 200；仅校验 status / content-type / expected vs actual length / ftyp 存在，不做 mdat 字符串搜索。
- 非 200 → 记 RECOVERY_NEEDS_REVIEW，继续下一条；不进行临时架构改写。
- 命名：`B003_{note_id}_FULL.mp4`。

### 浏览器状态枚举

`FULL_RESPONSE_SAVED` / `RESOURCE_DISCOVERED_NOT_SAVED` / `STREAM_ONLY` / `BLOCKED` / `WRONG_PAGE` / `NOT_IN_PILOT20` / `RECOVERY_ERROR`（另：非 200 属 `RECOVERY_NEEDS_REVIEW`）。

### 恢复波次

WAVE1=5 → WAVE2=5 → WAVE3=10。**Wave1 门**：同一系统性错误 ≥3/5 → STOP，修工具后再继续。

## 6. 本地验证规格（浏览器恢复 ≠ EXACT）

每条 `B003_{note_id}_FULL.mp4` 必须通过：

| 门 | 判据 |
|---|---|
| ffprobe | 容器真相 = ffprobe 唯一；时长、分辨率、编码、音轨 |
| ffmpeg decode | exit=0 全片可解码 |
| SHA256 | 记录；DB/既有资产精确反查 |
| TreeCut 指纹 | 感知 + 音频指纹（与 cover 交叉、与既有资产比对） |
| 文件大小门 | 与浏览器 actual_length / PublishedContent 预期一致 |
| 时长门 | 与发布整数秒（±容差）一致 |
| cover 交叉 | Published Cover（SHA256/width/height）与媒体首帧可对应 |

**EXACT_PUBLISHED_MEDIA 需 A-G 全部通过**（身份、字节、容器、解码、指纹、时长、cover 交叉）。

## 7. Canonical Asset 与转发簇

- **先查精确 SHA256** → REUSE 既有 asset_id，或才新建；**禁止每条笔记强制新建 asset**（转发共享同一 asset）。
- 转发检测：同 SHA256 / 感知+音频指纹 → `B003_PILOT20_REPOST_CLUSTERS_V3.json` 同簇；PublishedContent / title / cover / publish_time / Performance 每条笔记独立保留。
- 完整链：PublishedContent → Performance → Published Cover → EXACT_PUBLISHED_MEDIA → Canonical Asset → Segments（SceneDetector）→ ASR（WhisperEngine zh）→ Business Cognition V2.1。

## 8. 最终状态枚举（Pilot20 完成后）

`EXACT_PUBLISHED_MEDIA` / `MEDIA_IDENTITY_CONFLICT` / `RECOVERY_BLOCKED` / `STREAM_ONLY` / `INVALID_MEDIA` / `PENDING_REVIEW`。

**不要求 20/20 EXACT**；样本数与分层足够、无恢复偏倚时 PASS_WITH_LIMITATIONS 可接受。报告必须审计恢复偏倚（时间 / 时长 / 编码 / 表现分层集中度）。**STAGE3B_READY 仅在本报告后裁定，不因 Pilot1 单独成立。**

## 9. 本轮 31 问核验表（§53；浏览器相关项 = PENDING_BROWSER_RECOVERY）

| # | 问题 | 状态 |
|---|---|---|
| 1 | Pilot20 总样本是否 20 条 | ✅ 是（冻结 20 条全部待恢复；Pilot1=TECH_PILOT1 排除在正式样本外） |
| 2 | 是否重抽分层 | ✅ 否（保持冻结 HIGH 6/MID 7/LOW 7；7/7/6 描述 SUPERSEDED_BY_FROZEN_MANIFEST_AUDIT） |
| 2a | 19→20 是否样本扩容 | ✅ 否（Sample Definition Correction：未新增笔记，'Remaining19' 基于错误文字假设，Pilot1 从未属于 Frozen Pilot20） |
| 2b | 是否事后删除原 Pilot20 任一条 | ✅ 否（避免 POST_HOC_SAMPLE_SELECTION_BIAS，Frozen Manifest Truth 优先） |
| 3 | 是否新增恢复路线 | ✅ 否（沿用 Pilot1 验证路线） |
| 4 | 是否废弃随机 blob 拾取 | ✅ 已废弃 |
| 5 | 是否废弃 206 Range 逻辑 | ✅ V2_RANGE_LOGIC_DEFECT_CONFIRMED 废弃 |
| 6 | 是否废弃 mdat 字符串门 | ✅ 假阴性确认，容器真相=ffprobe |
| 7 | 是否废弃 note-detail 入口 | ✅ 废弃，正确入口=explore/{note_id} |
| 8 | 当前页身份门是否就位 | ✅ /explore/{note_id} 命中清单，否则 NOT_IN_PILOT20 |
| 9 | 是否保存敏感字段 | ✅ 否（query/token/cookie/auth/sign 全丢弃） |
| 10 | 媒体选择是否 video currentSrc+XHR 观察 | ✅ 是（非独立 fetch、非最大 blob） |
| 11 | 保存是否 Full GET 200 | ✅ 是（无 Range） |
| 12 | 保存门是否含 mdat 字符串 | ✅ 否（仅 status/content-type/length/ftyp） |
| 13 | 非 200 行为 | ✅ RECOVERY_NEEDS_REVIEW，继续 |
| 14 | 文件名规范 | ✅ B003_{note_id}_FULL.mp4 |
| 15 | 波次规划 | ✅ 5+5+10 |
| 16 | Wave1 系统性错误门 | ✅ ≥3/5 → STOP 修工具 |
| 17 | 本地验证是否 ffprobe 唯一容器真相 | ✅ 是 |
| 18 | ffmpeg decode 门 | ✅ exit=0 |
| 19 | SHA256 反查 | ✅ DB 精确反查 + 既有资产复用 |
| 20 | TreeCut 感知/音频指纹 | ✅ 纳入 EXACT 判据 |
| 21 | 文件大小门 | ✅ 与浏览器 actual_length 一致 |
| 22 | 时长门 | ✅ 对发布整数秒 |
| 23 | cover 交叉验证 | ✅ 首帧对 Published Cover |
| 24 | EXACT 是否 A-G 全过 | ✅ 是 |
| 25 | 是否强制新建 asset | ✅ 否（SHA256 复用优先） |
| 26 | 转发簇是否独立 | ✅ Repost Clusters V3；内容字段按笔记独立 |
| 27 | 是否要求 20/20 EXACT | ✅ 否（PASS_WITH_LIMITATIONS 可接受） |
| 28 | 是否审计恢复偏倚 | ✅ 是（时间/时长/编码/表现分层） |
| 29 | STAGE3B_READY 是否仅凭 Pilot1 | ✅ 否（须本报告后裁定） |
| 30 | 是否自动扩展 155 | ✅ 否 |
| 31 | 是否推进 DNA/模板/账户/导演/AutoCut | ✅ 否（全部禁止） |
| — | 浏览器恢复结果（19 条） | ⏳ PENDING_USER_BROWSER_RECOVERY |
| — | 本地验证 / EXACT 升级 | ⏳ 依赖浏览器产物 |
| — | Canonical asset 链接 / 转发簇 | ⏳ 依赖验证结果 |
| — | 分段 / ASR / 认知 / 端到端覆盖 | ⏳ 依赖 EXACT 集 |
| — | 恢复偏倚审计 | ⏳ 依赖恢复结果 |
| — | 最终裁定 | ⏳ STAGE3A7_PILOT20_PASS(_WITH_LIMITATIONS/_NEEDS_MEDIA_REPAIR/_RECOVERY_BIAS_DETECTED) |

## 10. 输出清单（§52，12 项）

| # | 文件（DATA_ROOT = runtime_data/temp/batch1） | 状态 |
|---|---|---|
| 0 | `B003_PILOT20_SAMPLE_DEFINITION_CORRECTION_V1.json` | ✅ 完成（19→20 修正裁定执行记录） |
| 1 | `B003_PILOT20_RECOVERY_MANIFEST_V2.json` | ✅ 完成（正式 20 条，无 Pilot1，字段合规） |
| 1a | `B003_PILOT20_REMAINING19_MANIFEST_V1.json` | ⚠️ 保留，标 `SUPERSEDED_SAMPLE_DEFINITION_ERROR`，禁止继续消费 |
| 2 | `B003_PILOT20_BROWSER_RECOVERY_RESULTS_V1.json` | ✅ 模板就位（引用 V2，PENDING） |
| 3 | `B003_PILOT20_MEDIA_VALIDATION_V1.json` | ✅ 桩就位（PENDING） |
| 4 | `B003_PLATFORM_REFERENCE_ASSETS_V5.json` | ✅ 桩就位（V4 含 Pilot1 EXACT，exact_count=1，TECH_PILOT 单独统计） |
| 5 | `B003_PILOT20_CANONICAL_ASSET_LINKS_V1.json` | ✅ 桩就位（PENDING） |
| 6 | `B003_PILOT20_REPOST_CLUSTERS_V3.json` | ✅ 桩就位（PENDING） |
| 7 | `B003_PILOT20_SEGMENT_VALIDATION_V1.json` | ✅ 桩就位（PENDING） |
| 8 | `B003_PILOT20_ASR_COVERAGE_V1.json` | ✅ 桩就位（PENDING） |
| 9 | `B003_PILOT20_BUSINESS_COGNITION_V21.json` | ✅ 桩就位（PENDING） |
| 10 | `B003_PILOT20_END_TO_END_COVERAGE_V1.json` | ✅ 桩就位（PENDING） |
| 11 | `B003_PILOT20_RECOVERY_BIAS_AUDIT_V1.json` | ✅ 桩就位（PENDING；仅 Formal Pilot20） |
| 12 | `B003_PILOT20_LOCAL_REVERSE_MATCH_V1.json` | ✅ 桩就位（PENDING） |

工具：`tools/B003_PILOT20_RECOVER_CURRENT_NOTE_V1.js`（node 语法核验通过，6,472 B）。
参考：Pilot1 全部产物（FULL_MEDIA_VALIDATION_FINAL_V1 / CANONICAL_ASSET_LINK_V1 / SEGMENT_VALIDATION_V1 / BUSINESS_COGNITION_V21 / END_TO_END_CHAIN_V1 / FULL_RESPONSE_PROBE_V1）。

## 11. 当前裁定与后续

**STAGE3A7_PILOT20_TOOLING_READY**

- sample_definition = **CORRECTED_AND_FROZEN**
- formal_pilot20 = **20**（HIGH 6 / MID 7 / LOW 7）
- pending = **20**
- tech_pilot1 = **EXACT / OUTSIDE_FORMAL_SAMPLE**
- PHASE4_STAGE3B_READY = **FALSE**（仅本报告后由 Formal Pilot20 结果裁定）

浏览器恢复已正式批准：**Formal Pilot20 全部 20 条**（无需再次 Stage 审批），Wave1=5 / Wave2=5 / Wave3=10，Wave1 门同种系统性错误 ≥3/5 → STOP 修工具。阶段性 STOP（不自动扩展、不推进任何被禁模块）。

用户浏览器执行后（每条 `explore/{note_id}` → 贴工具 → 播放 → `__B003Pilot20RecoverCurrent()` → 保存 `B003_{note_id}_FULL.mp4`，建议波次 5+5+10），把文件交回 Harness → 本地验证 → EXACT 升级 → 资产/分段/ASR/认知/端到端/偏倚 → 最终 Stage3A.7 统计（**TECH PILOT 1/1 与 FORMAL PILOT20 X/20 分开报告；High X/6 / Mid X/7 / Low X/7；禁止 X/21**）→ STAGE3B_READY 判定。
