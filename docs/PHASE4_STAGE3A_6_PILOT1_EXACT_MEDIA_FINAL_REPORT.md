# PHASE4 STAGE 3A.6 — PILOT1 EXACT MEDIA FINAL REPORT

> 状态：**STAGE3A6_PILOT1_END_TO_END_PASS · Pilot1 链路完全打通 · STOP（不自动扩 Pilot20）**
> 日期：2026-08-30
> Pilot1：note_id `6a8d75aa000000002503e3e2`《2米8现代简约岛台😭十几人聚餐够用》
> 纪律：未改原素材 · 未保存 signed URL/凭证 · 未进 Content DNA

---

## 1-8. FULL_V4 独立验证（用户提供 + Harness 复核）✅

| 项 | 结果 |
|---|---|
| file_size | **7579070 bytes**（与 Probe expected 完全一致）|
| SHA256 | `1c8bf25bc29e91b1c9e46529a460aa83f32919b7ce3dac5e1fb4bae1461a50a4` |
| MP4 container | **VALID**：ftyp(0,28) + moov(28,50909) + free + **mdat(50945,7528125)**；parsed=file=7579070，无缺失尾字节 |
| Browser mdat 误报 | **BROWSER_MDAT_GATE_FALSE_NEGATIVE_CONFIRMED**（实际 mdat 7528125 bytes 存在；JS 简易扫描器 false negative；Browser 字符串扫描永不作最终 Container Truth）|
| duration | **59.977256s**（published 59s，DURATION_COMPATIBLE）|
| decode | ffmpeg 全量 decode **exit 0 / 无 fatal error（DECODE_PASS）** |
| video | hevc/Main/720x1280/yuv420p/30fps/1799 frames/908kbps |
| audio | aac/HE-AAC/44100Hz/stereo/96kbps |
| visual | 同人物/岛台场景/内容一致（含"60公分以上的伸缩"字幕），PASS（不推断身份）|

## 9. PILOT1 IDENTITY VERDICT ✅

A-G 全部 PASS → **identity_confidence = EXACT_PUBLISHED_MEDIA**
PlatformReferenceAsset `6a8d75aa`：COVER_RECOVERED → **EXACT_PUBLISHED_MEDIA**

## 10-12. Canonical Asset 注册 ✅

- **asset_id = `ae35ab1981e84b1f9aa6942b937d8c90`**（TreeCut canonical assets 表，media_id=28252）
- 无并行身份系统；保留 PublishedContent → PlatformReferenceAsset → CanonicalAsset
- source_type = **DERIVED_FROM_PLATFORM_PUBLISHED_MEDIA**（非 ORIGINAL_LOCAL_EXPORT / RAW_ASSET / EDIT_PROJECT_SOURCE）
- 技术元数据已存：SHA256/duration/width/height/codec/fps/audio/provenance/note_id linkage（无 xsec/signed URL/cookie）
- TreeCut 原生指纹：perceptual/audio/keyframes 由现有服务生成（FFPROBE probe + Whisper ASR + scenes segments 已落库）

## 13. Cover 交叉验证 ✅

- `B003_PUBLISHED_COVER_REGISTRY_V3` 中 `6a8d75aa` 的 cover 已恢复
- 与 FULL_V4 内容（岛台/人物/场景）**COVER_VIDEO_COMPATIBILITY = PASS**（视觉内容一致，未发现冲突）

## 14. Segment Service 验证 ✅

- **20 个 segments**（`ae35ab19-S000` ~ `S019`）
- coverage = **0.921**（segment 总时长 / 59.98s 视频；场景检测覆盖主体内容）
- 边界/时长一致性通过

## 15. Business Cognition V2.1 ✅

```
USER_NEED STORAGE:          SUPPORTED (A)  ← "抽屉/薄抽/好收纳"
USER_NEED CHARGING_POWER:   SUPPORTED (A)  ← "轨道插座/一边打火锅一边充电"
BUSINESS_VALUE POWER_CONVENIENCE: SUPPORTED (A)
BUSINESS_VALUE FLEXIBLE_CAPACITY: SUPPORTED (A)  ← "伸缩/60公分以上"
BUSINESS_VALUE STORAGE_EFFICIENCY: CANDIDATE      ← Need→Value 解耦纪律生效
claim_status_counts: SUPPORTED 4 / CANDIDATE 1 / UNKNOWN 5
conflicts: 0
```

Consumer Policy 遵守：SUPPORTED=evidence-backed · CANDIDATE=soft · UNKNOWN=missing（非 absent）· Role/Theme=AFFINITY ONLY。

## 16-17. 端到端链路（全边 valid）✅

```
PublishedContent ✅ → Performance ✅ → Published Cover ✅ → EXACT_PUBLISHED_MEDIA ✅
→ Canonical Asset (ae35ab19) ✅ → Segments (20, 0.921) ✅ → ASR ✅ → Business Cognition V2.1 ✅
```

**STAGE3A6_PILOT1_END_TO_END_PASS**

## 18-20. Reverse Local Search ✅

- 现有 canonical Asset DB exact-SHA256 命中：**0**（无本地同源副本）
- Z:\ LEGACY_MIXED_MEDIA_POOL：未全量 hash（成本高，且 Z=LEGACY_POOL；本 Pilot 无先验命中需求）；若未来需要，先取 FULL_V4 指纹 → Z 轻量索引 reverse lookup
- 目录名不作身份证据

## 21-22. Pilot20 Gate + Stage3B

- **Pilot1 足够可靠，Pilot20 可推进**（Asset registration ✅ + fingerprints ✅ + Segment ✅ + Business Cognition ✅）
- 但按指令：**Pilot20 需 Stage 政策显式允许后才执行**（本轮不自动扩）
- **PHASE4_STAGE3B_READY = FALSE**（Pilot1 是技术验证，非 Stage3 收口；等 Pilot20 完成 + 政策确认）

## 产物
- `B003_PILOT1_FULL_MEDIA_VALIDATION_FINAL_V1.json`（SHA256 1c8bf25b 等）
- `B003_PLATFORM_REFERENCE_ASSETS_V4.json`（Pilot1 = EXACT，1/155）
- `B003_PILOT1_CANONICAL_ASSET_LINK_V1.json`（ae35ab19…）
- `B003_PILOT1_SEGMENT_VALIDATION_V1.json`（20 段，coverage 0.921）
- `B003_PILOT1_BUSINESS_COGNITION_V21.json`（4 SUPPORTED + 1 CANDIDATE）
- `B003_PILOT1_LOCAL_REVERSE_MATCH_V1.json`（DB 0 命中）
- `B003_PILOT1_END_TO_END_CHAIN_V1.json`（全边 valid）
- DB：assets(ae35ab19) + segments(20) + transcripts(ASR) 落库
- 本报告 `docs/PHASE4_STAGE3A_6_PILOT1_EXACT_MEDIA_FINAL_REPORT.md`

## 停点

**STOP** —— Pilot1 端到端 PASS。Pilot20 恢复需 Stage 政策显式允许（Pilot1 已验证的 Full GET 路线可复用：Playback Page → MP4 → HTTP 200 全响应 → 保存 → ffprobe 为准）。未自动扩 Pilot20 · 未进 Content DNA / Template / Account DNA。
