# P6 报告：人工选镜 + AI 排序建议 + FFmpeg 粗剪

> 日期：2026-08-19 | 阶段：P6（第二阶段）
> 结论：**P6 READY**（34/34 pytest + 真实素材粗剪验证通过）

---

## 1. 目标回顾

实现人工选镜后的 AI 辅助排序建议与 FFmpeg 粗剪。**AI 只建议不决定**（排序/时长/首镜/重复提示），粗剪输出可追溯（asset/segment/source/start/end）。

## 2. 新增模块

| 模块 | 功能 |
|---|---|
| `roughcut/engine.py` | FFmpeg 粗剪：rough_cut.mp4 + timeline.json + cuts.csv + subtitles.srt；concat demuxer 失败自动重编码兜底 |
| `roughcut/sort_advisor.py` | AI 排序建议：顺序/首镜/同素材重复提示/时长建议（只建议） |

## 3. 关键设计

### 粗剪（可追溯）
```
project_segments(selected) → 按 slot_order 排序
→ 解析每个 segment 的 source/start_ms/end_ms
→ FFmpeg concat demuxer（inpoint/outpoint 精确截取）
→ 失败自动重编码兜底（libx264 + aac）
→ timeline.json / cuts.csv / subtitles.srt 全量输出
```

### AI 排序（不替用户决定）
- 建议顺序：按模板槽位自然顺序
- 首镜建议：槽位 1（问题/强视觉）
- 重复提示：同 asset 多段 → 建议 EXCLUDE 一条
- 时长建议：总时长统计

## 4. CLI

```
--advise-sort PROJECT    AI 排序建议
--roughcut PROJECT OUT  生成粗剪
```

## 5. 测试：34/34 pytest 通过

```
tests/test_p6_roughcut.py         2 passed  ← P6 新增（排序建议/粗剪输出可追溯）
tests/test_p5_templates.py        4 passed
tests/test_p4_search.py           4 passed
tests/test_p3_classification.py   5 passed
tests/test_p2_scene_asr_ocr.py    5 passed
tests/test_p11_lifecycle.py       8 passed
tests/test_p1_assets.py           4 passed
tests/test_p1_migrate.py          2 passed
```

## 6. 真实素材验证

| 项 | 结果 |
|---|---|
| 选镜保存 | ✅ 4 个真实 segment 选入 PRJ-REAL-001 |
| AI 排序建议 | ✅ 顺序(1,2,3)、首镜、同素材多段重复提示、总时长 7.6s |
| FFmpeg 粗剪 | ✅ **rough_cut.mp4 10.3MB / 8.55s 可播放**（ffprobe 验证） |
| 可追溯输出 | ✅ timeline.json（asset/segment/source/start/end）+ cuts.csv + srt |

## 7. 遗留（写 BACKLOG）

- **字幕内容填充**：SRT 当前为占位（ASR 校正后填充，P7 或 UI 阶段）
- **BGM 混音**：粗剪未加 BGM（V1 明确不做复杂 BGM 匹配）
- **真实 Benchmark**：25-50s 视频制作耗时对比（QA 阶段，需完整流程）

## 8. Git

- 仓库：`yuhao8977-stack/treecut-v13`（公开）
- 新增：roughcut/engine.py + roughcut/sort_advisor.py + tests/test_p6_roughcut.py
- main.py：--advise-sort / --roughcut

---

## 9. 结论

**P6 READY** —— 人工选镜 → AI 排序建议 → FFmpeg 粗剪全链路真实可用。按总控指令继续 P7（CT03-CT12 模板扩展）。
