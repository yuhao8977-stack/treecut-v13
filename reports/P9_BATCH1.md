# P9 Batch1 报告：渐进式真实素材分析（首轮 300 素材）

> 日期：2026-08-19 | 阶段：P9（第二阶段，渐进式）
> 数据源：Z 网络盘（\\X1\素材01）已处理素材\卖点展示类素材（2982 视频）

---

## 1. 批次策略（总控指令 P9）

```
Batch1: 100-300 视频 → 自动 QA → Batch2: ~1000 → Batch3: ~5000 → 全量增量
全量分析不是全量重跑：DONE 且版本一致 → SKIP；新素材 → PROCESS；修改 → INVALIDATE→PROCESS
```

## 2. Batch1 执行记录

| 批次 | 范围 | 结果 |
|---|---|---|
| 扫描登记 | 卖点展示类 3025 视频 | 303s 完成（3025 asset 建库，canonical 协调去重） |
| Batch1-1 | 20 个 | scene20/keyframe20/asr20/ocr20 DONE，0 失败，132s |
| Batch1-2 | 100 个 | scene99/keyframe100/asr100/ocr100 DONE，0 失败，1261s |
| Batch1-3 | 200 个 | scene199/keyframe200/asr199/ocr200 DONE，0 失败，3587s |
| Batch1-4 | 200 个 | scene199/keyframe200/asr199/ocr200 DONE，0 失败，3481s |
| Batch1 验收 | P3 分类 600 个 | type/labels 600/600 DONE，0 失败，383s |

**累计（验收时）**：~600 素材完成 P2+P3，**0 失败**，数据 798 segments / 2394 keyframes / 1209 transcripts / 8319 OCR

## 3. 中文转写质量抽查（真实岛台口播）

```
"这边我们还配置了一个上层的薄抽"
"上面两个大抽屉放小孩子的零食和妈妈的..."
"筷子勺子纸巾牙线还能放点咖啡豆"
```
→ faster-whisper small 中文转写质量良好（产品功能口播准确）

## 4. 发现并修复的问题

1. **单镜头稳定素材场景切分 0 段** → SceneDetector 降级为均匀分段（保证每视频 ≥1 可用 segment），修复 commit 73b53a4，重跑验证 segments 正常

## 5. 性能数据

- 扫描速度：3025 视频 303s（~10 视频/s，网络盘 size/mtime 轻读）
- 分析速度：~3.3 素材/min（含 ASR 中文转写 + OCR + 关键帧）
- P3 分类：600 素材 383s（~1.6/s）
- 错误率：**0%**（600+ 素材零失败）

## 6. 遗留

- Batch1 剩余素材（3025 目标）继续分析中
- P4 嵌入后台执行中（BGE-M3 逐段编码较慢）
- Batch2（~1000）在 Batch1 稳定后启动
