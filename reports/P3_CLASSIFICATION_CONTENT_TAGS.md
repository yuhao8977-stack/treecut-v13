# P3 报告：成片/原片分类 + 重复识别 + TC_CONTENT_TAGS + 人工纠错

> 日期：2026-08-19 | 阶段：P3（第二阶段）
> 结论：**P3 READY**（24/24 pytest + 真实成片验证通过）

---

## 1. 目标回顾

实现素材理解层：成片/原片/半成品分类（规则特征组合，非纯 VLM）、重复/近重复识别（只标记不删除）、TC_CONTENT_TAGS 内容运营标签（与账号编号完全解耦）、人工纠错（human_override 优先）。

## 2. 新增模块

| 模块 | 功能 |
|---|---|
| `content_tags.py` | TC_CONTENT_TAGS 词典（9 类 ~70 标签：SCENE/STATE/FEATURE/ACTION/SHOT/PERSON/CRAFT/STYLE/USE_CASE），与 B001-B010 账号完全解耦 |
| `classify/asset_type.py` | 成片/原片规则分类器（硬字幕比例+切镜频率+口播+音乐+时长+画面文字 → RAW/FINISHED/SEMI_FINISHED/UNKNOWN + confidence + reason_codes） |
| `library/classification_store.py` | labels / duplicate_groups / asset_types 三表（全部经 asset_id 关联） |
| `analysis/p3_worker.py` | 统一 worker：duplicate 阶段承载成片分类 + labels 阶段规则标签 + 全库精确重复分组 |

## 3. 关键设计

### 成片/原片分类（不依赖 VLM）
```
hard_subtitle_ratio ≥0.5 → +0.35（强信号）
cut_rate ≥0.3 → +0.2
has_speech → +0.2
has_music → +0.1
text_items ≥10 → +0.15
duration >180s → 原片 +0.3
≥0.6 → FINISHED | ≥0.3+原片 → RAW | ≥0.3 → SEMI_FINISHED | else UNKNOWN
```

### 人工纠错一等公民
- `human_override=1` 的标签**永远优先**，模型标签不覆盖
- `--add-label ASSET_ID CATEGORY LABEL` 命令行人工添加
- source=rule/model/human 三源分离

### TC_CONTENT_TAGS
- 9 类 ~70 标签（用户确认清单）
- 文件名/路径规则标签（P3 当前）；视觉标签（SigLIP/Florence）写 BACKLOG 为 P3.1 增强

## 4. 测试：24/24 pytest 通过

```
tests/test_p3_classification.py   5 passed  ← P3 新增（分类规则/store schema/人工覆盖/重复分组/worker 生命周期）
tests/test_p2_scene_asr_ocr.py    5 passed  ← P2 回归
tests/test_p11_lifecycle.py       8 passed  ← P1.1 回归
tests/test_p1_assets.py           4 passed  ← P1 回归
tests/test_p1_migrate.py          2 passed  ← P1 回归
```

## 5. 真实素材验证（2 个真实成片）

| 项 | 结果 |
|---|---|
| 成片/原片分类 | ✅ 2 个真实成片 → **FINISHED**（有硬字幕+口播+切镜，符合预期） |
| 规则标签 | ✅ 运行完成（文件名 "3.9 产品1.mp4" 无标签关键词 → 0 命中，合理） |
| 人工纠错 | ✅ --add-label 添加 human 标签成功，human_override=1 |
| 精确重复分组 | ✅ 全库 fingerprint 分组引擎就绪（当前库无重复 → 0 组） |

## 6. 遗留（写 BACKLOG）

- **视觉标签**：SigLIP/Florence 关键帧零样本分类（TC_CONTENT_TAGS 对编号文件名的 0 命中问题，P3.1 增强）
- **近重复**：L2 pHash + L3 embedding（当前只做 L1 exact hash 分组）
- **BGM 检测**：has_music 当前保守 False（音频分类 P3.1）
- **标注评估集**：100-200 条人工标注（QA 阶段建立）

## 7. Git

- 仓库：`yuhao8977-stack/treecut-v13`（公开）
- 新增：content_tags.py / classify/ / library/classification_store.py / analysis/p3_worker.py / tests/test_p3_classification.py
- main.py：--p3-run/--p3-status/--labels/--add-label

---

## 8. 结论

**P3 READY** —— 成片/原片分类、重复分组、TC_CONTENT_TAGS、人工纠错全部接入生命周期并通过测试。按总控指令继续 P4（检索）。
