# P2 报告：场景切分 + 关键帧 + ASR + OCR

> 日期：2026-08-19 | 阶段：P2（第二阶段）
> 结论：**P2 READY**（代码 + 测试 + Z 盘真实素材验证全部通过）

---

## 1. 目标回顾

将视频从 Asset 拆为 Segment（镜头），生成关键帧，完成 ASR 语音转写与 OCR 字幕识别。**所有 worker 接入 P1.1 should_process 生命周期，禁止绕过**，确保数万素材不重复分析。

## 2. 新增模块（treecut-v13 仓库）

| 模块 | 功能 |
|---|---|
| `scenes/detector.py` | PySceneDetect ContentDetector 场景切分（无依赖时均匀分段降级） |
| `keyframes/extractor.py` | 每 segment 首/中/尾 + 清晰度筛选 2–5 帧；中文路径兼容写盘 |
| `asr/engine.py` | faster-whisper（默认 small / CPU int8 / 离线 HF 缓存）；raw+corrected 分离 |
| `ocr/engine.py` | RapidOCR 硬字幕检测（只处理关键帧，禁逐帧）；bbox/coverage/subtitle_flag |
| `library/segments.py` | segments / keyframes / transcripts / ocr_text 四表（全部经 asset_id 关联） |
| `analysis/p2_worker.py` | 统一 worker：should_process → claim → run → save → DONE |

## 3. 数据表（P2 范围）

```sql
segments(segment_id, asset_id, scene_no, start_ms, end_ms, duration_ms, quality_score, algorithm_version)
keyframes(frame_id, segment_id, asset_id, timestamp_ms, image_path, sharpness, brightness, selected)
transcripts(asset_id, segment_id, start_ms, end_ms, text_raw, text_corrected, language, confidence, model_name, model_version)
ocr_text(asset_id, frame_id, frame_timestamp_ms, text, bbox, subtitle_flag, coverage, confidence, ocr_model, ocr_model_version)
```

## 4. CLI 命令

```
--p2-run COUNT         处理 COUNT 个素材的 scene/keyframe/asr/ocr
--p2-status            阶段统计 + 结果计数
--p2-no-asr/--p2-no-ocr   跳过对应阶段
```

## 5. 真实素材验证（Z 盘 B组更新视频，2 个真实成片）

| 项 | 结果 |
|---|---|
| 场景切分 | ✅ 真实成片 20 segments（scenedetect 0.7.1 ContentDetector） |
| 关键帧 | ✅ 60 张 jpg 写盘成功（首/中/尾，中文路径兼容） |
| ASR | ✅ faster-whisper small CPU 15s 转写真实中文口播 23 段（"新家第一个敲定的家具就是回头了两年前那家岛台…"） |
| OCR | ✅ RapidOCR 142 条文字，**47 条硬字幕**（"新家第一个敲定的家具"等字幕正确识别，subtitle_flag 区分字幕/非字幕） |
| 幂等 | ✅ 再次运行 scanned:0 remaining:0（**全部 SKIP，零重复处理**） |
| 增量 | ✅ 二次扫描 unchanged（不重复 probe/hash） |

## 6. 测试：19/19 pytest 通过

```
tests/test_p2_scene_asr_ocr.py    5 passed  ← P2 新增（segment 存储/场景检测/均匀降级/worker 生命周期/关键帧提取）
tests/test_p11_lifecycle.py       8 passed  ← P1.1 回归
tests/test_p1_assets.py           4 passed  ← P1 回归
tests/test_p1_migrate.py          2 passed  ← P1 回归
```

## 7. 修复的代码 bug（测试与真实素材暴露）

1. **cv2.imwrite 中文路径静默失败**（关键帧 0 文件）→ 改用 imencode + 二进制写盘
2. **cv2.imread 中文路径返回 None**（OCR bbox 计算失败）→ np.fromfile + imdecode
3. **faster-whisper GPU 加载失败**（cublas64_12.dll 缺失）→ 默认 device="cpu"
4. **v13 bootstrap 把 HF_HOME 指向空目录**（离线找不到模型）→ 回退用户级 HF 缓存

## 8. 遗留（写 BACKLOG，不在 P2 范围）

- faster-whisper small vs medium 中文口播 Benchmark（当前 small 有"岛台→导台"等音近错误，P3 前可对比 medium）
- 场景切分阈值调优（真实素材 20 段合理，不同品类需抽查）
- 关键帧差异度筛选（当前首/中/尾均匀，后续可加内容差异去重）

## 9. Git

- 仓库：`yuhao8977-stack/treecut-v13`（公开）
- 新增：scenes/ keyframes/ asr/ ocr/ 模块 + library/segments.py + analysis/p2_worker.py + tests/test_p2_scene_asr_ocr.py
- 未上传：视频/关键帧/模型/运行库（.gitignore 覆盖）

---

## 10. 结论

**P2 READY** —— 场景切分、关键帧、ASR、OCR 全部接入生命周期并真实素材验证通过。按总控指令继续 P3（成片/原片 + 重复识别 + TC_CONTENT_TAGS）。
