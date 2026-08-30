# PHASE4 STAGE 3A.6 — PILOT1 FULL RESPONSE RECOVERY V3

> 状态：**PILOT1_FULL_RESPONSE_RECOVERY_TOOL_READY · 待用户执行 `__B003RecoverFullV3()` · STOP**
> 日期：2026-08-30
> 前置：Probe = HTTP 200 / video/mp4 / 7.58MB 完整响应；V2 Range 逻辑缺陷已确认并修正
> 纪律：不扩 Pilot20 · 不进 Segment/Cognition/Content DNA · 不绕过访问控制

---

## 0-2. 浏览器实测结果 ✅

```
__B003RangeProbe() →
  status = 200
  content_type = video/mp4
  content_length = 7579070（≈7.58MB）
  content_range = ""（无 Range → 完整响应）
  accept_ranges = ""
Browser Observer 实际观察到 ≈7401KB video blob（与 7579070 bytes 高度一致）
```

**FULL VIDEO RESOURCE 高度可能在浏览器正常会话中完整取得。**

**明确**：不判 RANGE_RECONSTRUCTION_BLOCKED / VIDEO_RECOVERY_BLOCKED——当前失败层是 **RECOVERY_TOOL_LOGIC**（非平台 BLOCK）。

## 3-4. V3 工具（优先路线：Full GET，不带 Range）✅

**`tools/B003_PILOT1_FULL_RESPONSE_RECOVERY_V3.js`**（node 语法验证通过）：
- 复用当前页面已观察到的**同一个 video/mp4 resource**（资源身份绑定，仅内存）
- **普通 GET（不设置 Range header）→ response.arrayBuffer()**
- **Length Gate**：actual ≈ 7579070（±1% 合理范围）；明显几百 KB/1-2MB → PARTIAL_RESPONSE 不保存
- **MP4 Container Gate**：ftyp + moov + (mdat 或 moof+mdat)
- 保存 `B003_6a8d75aa000000002503e3e2_FULL_V3.mp4`（不覆盖 V1 404KB / 其它 FULL 测试文件）
- Console 只输出：resource_selected/content_type/expected_length/actual_length/container_check/download_status；**不打印 URL/query/凭证**
- 执行命令：**`__B003RecoverFullV3()`**

## 12-14. V2 Range 逻辑修正 ✅

- **206 = EXPECTED SUCCESS**（对 Range Request 正常成功），不得判 FIRST_RANGE_FAILED
- V2 已加 `V2_RANGE_LOGIC_DEFECT_CONFIRMED` 头注释：Probe=200 场景走 V3 Full GET；Range 仅作 206 fallback
- **不要求用户第三次运行 `__B003RangeReconstruct(probe)`**

## 15-20. FULL 文件本地验证（文件到位时执行）

1. ffprobe：duration/width/height/video_codec/audio_codec/fps/bitrate/file_size
2. **Duration Gate**：预期 ≈59s（允许 container rounding，58-60s）；明显偏离 → MEDIA_IDENTITY_CONFLICT
3. **Decode Gate**：ffmpeg decode validation PASS
4. **Hash Gate**：SHA256 + perceptual video fingerprint + audio fingerprint
5. **Cover 交叉验证**：note 6a8d75aa 已恢复封面 ↔ FULL_V3 keyframes 视觉兼容
6. **EXACT 升级条件**：Published Playback Resource + Full 7.58MB + Valid MP4 + Duration≈59s + Decode PASS + Cover Compatible → EXACT_PUBLISHED_MEDIA

## 21. 当前状态

```
RESOURCE_DISCOVERY   = VALIDATED
FULL_RESOURCE_PROBE  = VALIDATED
RECOVERY_V1          = PARTIAL_INVALID
RECOVERY_V2          = TOOL_LOGIC_DEFECT（已修正标注）
EXACT_PUBLISHED_MEDIA = FALSE
PHASE4_STAGE3B_READY = FALSE
```

## 产物
- `B003_PILOT1_RECOVERY_V2_FAILURE_ANALYSIS.json`（V2 逻辑缺陷分析）
- `B003_PILOT1_FULL_RESPONSE_PROBE_V1.json`（Probe 正式记录：200/7.58MB）
- `tools/B003_PILOT1_FULL_RESPONSE_RECOVERY_V3.js`（Full GET 恢复工具）
- `tools/B003_PILOT1_RANGE_AWARE_RECOVERY_V2.js`（206 语义修正 + V2_DEFECT 标注）
- 本报告 `docs/PHASE4_STAGE3A_6_PILOT1_FULL_RESPONSE_RECOVERY_V3.md`

## 停点

**STOP** —— 等你浏览器执行 `__B003RecoverFullV3()` → 保存 `FULL_V3.mp4` → 发我核验（ffprobe/duration/decode/hash/cover）。未扩 Pilot20 · 未进 Segment/Cognition/Content DNA。
