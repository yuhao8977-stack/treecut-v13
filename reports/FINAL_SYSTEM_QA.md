# P8 报告：全系统 QA（FINAL_SYSTEM_QA）

> 日期：2026-08-19 | 阶段：P8（第二阶段）
> 结论：**SYSTEM_QA_READY**（QA1-QA10 全部通过）

---

## QA 结果汇总

| QA 项 | 检查内容 | 结果 |
|---|---|---|
| QA1 单元测试 | 37/37 pytest（9 测试文件） | ✅ PASS |
| QA2 集成测试 | scan→lifecycle→scene→keyframe→ASR→OCR→labels→embedding→search→template→roughcut 全链路 | ✅ PASS |
| QA3 数据库完整性 | 0 orphan / 0 无效状态 / 0 外键违规 / 阶段完整 | ✅ PASS |
| QA4 重启恢复 | PROCESSING→PENDING 恢复（pytest test_g）+ 真实库无残留 running | ✅ PASS |
| QA5 重复分析 | 二次运行 scanned:0 remaining:0（全 SKIP）| ✅ PASS |
| QA6 检索 Benchmark | 原库"岛台 收纳 插座"→2 真实成片（vec 0.60/0.54）| ✅ PASS |
| QA7 模板 Benchmark | CT01 槽 1 → 5 候选 0.012s | ✅ PASS |
| QA8 粗剪 | 2 clips 4.07s 粗剪生成（可追溯）| ✅ PASS |
| QA9 资源 | E 盘 285GB 可用 / Z 盘 12TB 可用 | ✅ PASS |
| QA10 Git | 工作树干净、无媒体/模型/DB/Secret 违规、远程同步 | ✅ PASS |

## QA3 数据全景（真实库）

```
total_assets: 2          segments: 43       keyframes: 129
transcripts: 49          ocr_text: 294      labels: 1（人工）
probe/scene/keyframe/asr/ocr/duplicate/labels/embedding: 全部 DONE
```

## 系统能力清单（P0-P8 完整交付）

- ✅ 素材扫描 + 增量识别（NEW/CHANGED/MOVED/MISSING/UNCHANGED）
- ✅ Canonical Asset Registry（asset_id 唯一身份）
- ✅ 生命周期状态机（10 阶段 × 9 状态）+ should_process 幂等 + 依赖图
- ✅ 场景切分 / 关键帧 / ASR（faster-whisper 中文）/ OCR（RapidOCR 硬字幕）
- ✅ 成片/原片分类 / 精确重复分组 / TC_CONTENT_TAGS / 人工纠错
- ✅ 混合检索（FTS5 trigram + BGE-M3/FAISS + 标签 + 质量 + 去重）
- ✅ CT01-CT12 模板（78 槽位）+ 候选推荐（带原因）
- ✅ 人工选镜 + AI 排序建议 + FFmpeg 粗剪（可追溯）

## 已知问题 / 遗留（BACKLOG）

1. 视觉标签（SigLIP/Florence）未接入——P3 仅规则标签，编号文件名 0 命中
2. 近重复识别仅 L1 exact hash（L2 pHash / L3 embedding 未实现）
3. BGM 检测 has_music 保守 False
4. SRT 字幕为占位（ASR 校正后填充）
5. UI 9 页界面未开发（当前 CLI）
6. 标注评估集（100-200 条）未建立
7. Z 盘全量扫描未执行（P9 渐进式）

## Git

- 仓库：`yuhao8977-stack/treecut-v13`（公开）
- 全部 commit 已推送，工作树干净

---

## 结论

**SYSTEM_QA_READY** —— 系统开发完成且 QA 通过。按总控指令进入 P9（渐进式真实素材分析）。
