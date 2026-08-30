# Phase 4 Stage 3A.7 — B003 Pilot20 Published Media Recovery（工具与就绪报告）

- 日期：2026-08-30
- 阶段：Stage 3A.7（Pilot20 已发布媒体恢复）
- 最终状态：**STAGE3A7_PILOT20_TOOLING_READY（等待用户浏览器执行 19 条恢复）** — 最终裁定（PASS / PASS_WITH_LIMITATIONS / NEEDS_MEDIA_REPAIR / RECOVERY_BIAS_DETECTED）仅在浏览器恢复 + 本地验证完成后出具
- 前序：Stage 3A.6 Pilot1 EXACT PUBLISHED MEDIA 端到端 PASS（commit `c46b1b8`）

---

## 1. 范围与架构师批准（§0-55 固化）

架构师批准（Stage3A.7 约束）：

- **Pilot20 = 总共 20 条**。Pilot1 已完成，本轮只恢复**剩余 19 条**，不是再加 20 条。
- **不再研发新恢复路线**；目标从"研究怎么恢复视频"切换为"**验证路线在高中低表现 20 条上稳定，形成可靠媒体样本集**"。
- 禁止自动扩展到 155 条（155 库身份已建，媒体恢复不在本轮）。
- 禁止：Content DNA、Template Mining、Account DNA、Script Intelligence、Director、AutoCut。

## 2. 数据事实澄清（必须知会用户）

- **Pilot1（note 6a8d75aa）不在本轮 20 条清单内**。Pilot1 是 Stage3A.6 的独立技术侦察样本（KNOWN_GOOD_REFERENCE / PILOT20_SAMPLE_01），程序化核验过：Pilot20 V1/V2/V3 清单均不含 6a8d75aa。
- 架构师表述"剩余 19 条"与本轮清单 **20 条**的差异 = **Pilot1 的位置归属**：20 条 = Pilot1（已完成）+ 19 条（本轮恢复），清单本身保持原 Pilot20 的 20 条选择（HIGH 7/MID 7/LOW 6 的原始分层，无重抽）。
- 本报告清单 `B003_PILOT20_REMAINING19_MANIFEST_V1.json` 记录 20 条待恢复（HIGH 6/MID 7/LOW 7 —— 该 JSON 独立分层，Pilot1 单独挂靠为参考）。
- **待用户确认**：20 条清单是否为预期恢复集（见末尾用户操作指令）。

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
| 1 | Pilot20 总样本是否 20 条 | ✅ 是（清单 20；Pilot1 已完成为参考，不在清单） |
| 2 | 是否重抽分层 | ✅ 否（保持原 HIGH 7/MID 7/LOW 6 选择） |
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
| 1 | `B003_PILOT20_REMAINING19_MANIFEST_V1.json` | ✅ 完成（20 条，含 cover sha256/路径） |
| 2 | `B003_PILOT20_BROWSER_RECOVERY_RESULTS_V1.json` | ✅ 模板就位（PENDING） |
| 3 | `B003_PILOT20_MEDIA_VALIDATION_V1.json` | ✅ 桩就位（PENDING） |
| 4 | `B003_PLATFORM_REFERENCE_ASSETS_V5.json` | ✅ 桩就位（V4 含 Pilot1 EXACT，exact_count=1） |
| 5 | `B003_PILOT20_CANONICAL_ASSET_LINKS_V1.json` | ✅ 桩就位（PENDING） |
| 6 | `B003_PILOT20_REPOST_CLUSTERS_V3.json` | ✅ 桩就位（PENDING） |
| 7 | `B003_PILOT20_SEGMENT_VALIDATION_V1.json` | ✅ 桩就位（PENDING） |
| 8 | `B003_PILOT20_ASR_COVERAGE_V1.json` | ✅ 桩就位（PENDING） |
| 9 | `B003_PILOT20_BUSINESS_COGNITION_V21.json` | ✅ 桩就位（PENDING） |
| 10 | `B003_PILOT20_END_TO_END_COVERAGE_V1.json` | ✅ 桩就位（PENDING） |
| 11 | `B003_PILOT20_RECOVERY_BIAS_AUDIT_V1.json` | ✅ 桩就位（PENDING） |
| 12 | `B003_PILOT20_LOCAL_REVERSE_MATCH_V1.json` | ✅ 桩就位（PENDING） |

工具：`tools/B003_PILOT20_RECOVER_CURRENT_NOTE_V1.js`（node 语法核验通过，6,472 B）。
参考：Pilot1 全部产物（FULL_MEDIA_VALIDATION_FINAL_V1 / CANONICAL_ASSET_LINK_V1 / SEGMENT_VALIDATION_V1 / BUSINESS_COGNITION_V21 / END_TO_END_CHAIN_V1 / FULL_RESPONSE_PROBE_V1）。

## 11. 当前裁定与后续

**STAGE3A7_PILOT20_TOOLING_READY** —— 清单、工具、验证规格、输出桩全部就位。阶段性 STOP（不自动扩展、不推进任何被禁模块）。

用户浏览器执行后（每条 `explore/{note_id}` → 贴工具 → 播放 → `__B003Pilot20RecoverCurrent()` → 保存 `B003_{note_id}_FULL.mp4`，建议波次 5+5+10），把文件交回 Harness → 本地验证 → EXACT 升级 → 资产/分段/ASR/认知/端到端/偏倚 → 最终 STAGE3A.7 裁定 → STAGE3B_READY 判定。
