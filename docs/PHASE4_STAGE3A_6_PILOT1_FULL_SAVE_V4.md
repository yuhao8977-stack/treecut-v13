# PHASE4 STAGE 3A.6 — PILOT1 FULL SAVE V4

> 状态：**PILOT1_FULL_RESPONSE_SAVE_TOOL_READY · 待用户执行 `__B003SaveFullV4()` · STOP**
> 日期：2026-08-30
> 前置：V3 Full GET 成功（7579070 = 7579070）；Browser mdat 简易扫描 FALSE = INCONCLUSIVE（非 INVALID）
> 纪律：不扩 Pilot20 · 不进 Segment/Cognition/Content DNA · 不绕过访问控制

---

## 0-2. 最新浏览器结果 ✅

```
V3 Full GET：
  expected_length = 7579070
  actual_length   = 7579070（完全一致）
  browser_gate: ftyp TRUE / moov TRUE / mdat_or_moof FALSE → V3 返回 CONTAINER_GATE_FAILED
```

**Browser Gate 不是最终 Container Truth**：它只是简易 byte-pattern 检测器，非 ISO BMFF parser / ffprobe / ffmpeg demuxer。`mdat_or_moof=FALSE` 只表示 JS 检测方法没找到；在 **actual==expected + ftyp TRUE + moov TRUE** 下，不能证明文件非完整 MP4。

**状态修正**：`CONTAINER_VALIDATION_PENDING_FFPROBE`（非 CONTAINER_INVALID）：
```
RESOURCE_DISCOVERY = VALIDATED · FULL_RESPONSE_GET = VALIDATED
BYTE_LENGTH_GATE = PASS · BROWSER_FTYP_GATE = PASS · BROWSER_MOOV_GATE = PASS
BROWSER_MDAT_GATE = INCONCLUSIVE
```

## 3-6. V4 保存工具 ✅

**`tools/B003_PILOT1_FULL_RESPONSE_SAVE_V4.js`**（node 语法验证通过）：
- 重新取得同一 Pilot1 media resource 的普通 HTTP 200 完整响应（不带 Range）
- **保存前只验证**：status==200 · content-type 含 video/mp4 · actual==7579070（±1% 合理）· ftyp==TRUE
- **不再因 mdat/moof 简易扫描失败阻止落盘**
- 保存 `B003_6a8d75aa…_FULL_V4.mp4`（不覆盖 V1/V2/V3）
- **落盘身份 = FULL_RESPONSE_BYTES_UNVERIFIED_CONTAINER**（非 EXACT_PUBLISHED_MEDIA，待 ffprobe）
- Console 只输出 status/content type/expected/actual/ftyp/save success；不打印 URL/凭证
- 执行命令：**`__B003SaveFullV4()`**

## 7-8. 安全 + 停 Browser 分析 ✅

- 完整 media URL 仅浏览器内存；不保存 xsec_token/cookie/auth/session/signature/signed query
- **V4 保存成功后 STOP Browser-side media analysis** → 交 Harness 本地验证

## 9-16. 本地验证（FULL_V4 到位时执行）

1. **ffprobe**：format_name/duration/size/bit_rate + video(codec/width/height/pix_fmt/avg_frame_rate) + audio(codec/sample_rate/channels)
2. **Duration Gate**：published 59s → 58-60s = DURATION_COMPATIBLE；明显偏离 → MEDIA_IDENTITY_CONFLICT
3. **Full Decode Gate**：ffmpeg 完整 decode validation（不重编码），无 fatal error → DECODE_PASS
4. **MP4 Container 最终 Truth**：以 ffprobe demux + ffmpeg decode 为 VALID_MEDIA_CONTAINER（不再以 JS 字符串搜索 mdat/moof）
5. **Hash/Fingerprint**：SHA256 + perceptual video fingerprint + audio fingerprint
6. **Cover Cross Validation**：note 6a8d75aa 已恢复 cover ↔ FULL_V4 sparse keyframes 视觉兼容

**EXACT 升级条件（全满足）**：A Published Playback resource · B 7579070 bytes · C ffprobe PASS · D duration≈59s · E decode PASS · F cover compatible

**若 ffprobe 仍失败** → `FULL_RESPONSE_NOT_STANDALONE_MP4`（检查特殊 fragment/reference format；不再用 Browser 字符串猜测）

## 17. Pilot20 冻结 ✅

Pilot20 / 155 / Segment / Cognition 全部 FROZEN，直到 FULL_V4 本地验证完成。

## 产物
- `B003_PILOT1_BROWSER_CONTAINER_GATE_ANALYSIS_V1.json`（mdat=INCONCLUSIVE，最终 Truth 交 ffprobe）
- `tools/B003_PILOT1_FULL_RESPONSE_SAVE_V4.js`（保存工具）
- `B003_PILOT1_FULL_MEDIA_VALIDATION_V2.json`（本地验证模板）
- 本报告 `docs/PHASE4_STAGE3A_6_PILOT1_FULL_SAVE_V4.md`

## 停点

**STOP** —— 等你浏览器执行 `__B003SaveFullV4()` → 保存 FULL_V4.mp4 → 发我，我执行 ffprobe/decode/duration/hash/cover 核验 → EXACT_PUBLISHED_MEDIA。未扩 Pilot20 · 未进 Segment/Cognition/Content DNA。
