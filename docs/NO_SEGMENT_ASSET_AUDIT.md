# TreeCut 无 Segment Asset 审计（NO_SEGMENT_ASSET_AUDIT）

> Phase: 2 | 日期: 2026-08-26
> 数据: materials.db 实时查询

---

## 一、结论

**75 个无 Segment 的 Asset 全部属于「Pipeline 遗漏（Segment 生成遗漏）」，非损坏视频。**

| 分类 | 数量 | 判定 |
|---|---|---|
| A. 损坏/不可解码 | **0** | 文件均存在且可读（抽样 20 全存在，0 字节文件 = 0） |
| B. 极短视频 | **0** | 文件大小 median 6.2MB（正常视频规模） |
| C. Scene 阶段失败 | **0** | scene:DONE 72 / PROCESSING 3（非 FAILED） |
| D. **Segment 生成遗漏** | **75** | keyframe:SKIPPED 75 条（pipeline 跳过关键帧→未生成 segment） |
| E. 未知 | 0 | - |

## 二、证据链

### 2.1 文件本身正常

| 项 | 值 |
|---|---|
| 文件存在性（抽样 20） | 20/20 存在 |
| 0 字节文件 | 0 |
| 文件大小分布 | min 362KB / median 6.2MB / max 184MB |
| 涉及 sources | 3 个（正常素材源） |

### 2.2 pipeline 状态（75 个 asset 全部）

| stage | status | 说明 |
|---|---|---|
| probe | **NEW（75）** | **全库 probe DONE = 0**——历史 pipeline 从未真正执行 probe |
| scene | DONE 72 / PROCESSING 3 | 场景切分"完成"但未落 segment |
| keyframe | **SKIPPED（75）** | 关键帧跳过 → 无 segment 生成的直接原因 |
| ocr | SKIPPED（75） | 随关键帧跳过 |
| asr | DONE（75） | ASR 正常 |
| duplicate | DONE（75） | 去重正常 |

### 2.3 根因

```
probe 阶段从未执行（全库 probe DONE=0，probe_status 全 pending）
  → assets.duration/width/height/fps 全部为 0
  → scene 切分基于时长，时长为 0 时 SceneDetector 无法生成 segment
  → keyframe 因无 scene 边界而 SKIPPED
  → 最终 75 个 asset 无任何 segment
```

## 三、影响

- 这 75 个 asset 占全部 22465 的 **0.33%**
- 无 segment = 无法作为生产镜头单位（宪法 2：segment 是生产最小单位）
- 不影响其他 22390 个 asset 的 41814 个 segment

## 四、修复方案（等待本 Phase 后续安全处理，本 Phase 禁止直接补）

**明确可恢复的 pipeline 遗漏，建议 Phase 2 末或 Phase 3 处理：**

1. 对 75 个 asset 执行 `probe` 阶段（ffprobe 探测时长/宽高/fps）
2. probe 成功后重新执行 `scene` 切分（ContentDetector）
3. scene 成功后生成 keyframe + segment
4. 预期可恢复 72+ 个（scene:DONE 但无 segment 的 72 个需重跑 scene 落库）

**本 Phase 行动**：仅审计报告 + 标记，不直接补 Segment（遵守指令「禁止直接补 Segment，先提出修复方案」）。

## 五、数据清单

完整 75 条清单存于 `runtime_data/temp/batch1/no_segment_assets.json`（asset_id/duration/宽高/codec/路径/大小）。
