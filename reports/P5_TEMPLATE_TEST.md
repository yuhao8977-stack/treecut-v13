# P5 报告：CT01/CT02 模板引擎 + 候选镜头推荐

> 日期：2026-08-19 | 阶段：P5（第二阶段）
> 结论：**P5 READY**（32/32 pytest + 真实素材模板推荐验证通过）

---

## 1. 目标回顾

实现模板驱动素材调用：CT01/CT02 内容模板（版本化，与账号 B001-B010 完全解耦），每槽位自动推荐 3-10 候选镜头（带推荐原因，可解释非黑盒），用户 SELECT/BACKUP/EXCLUDE。

## 2. 新增模块

| 模块 | 功能 |
|---|---|
| `templates/definitions.py` | CT01（8 槽位）+ CT02（9 槽位）JSON 定义（版本化） |
| `templates/engine.py` | content_templates/template_slots/project_segments 三表 + 候选推荐引擎 + 选镜保存 |

## 3. 槽位结构

```json
{"order": 1, "name": "问题/强视觉", "min_duration": 1.5, "max_duration": 3.0,
 "semantic_query": "小户型岛台强视觉整体或伸缩变化",
 "required_tags": ["客户家"], "preferred_tags": ["无人"], "avoid_tags": []}
```

## 4. 候选推荐逻辑

```
候选池 = 所有 segment（available 素材）
→ 硬过滤（required_tags 必须命中，avoid_tags 排除）
→ 去重惩罚（duplicate_groups 成员 -0.15）
→ 标签匹配（preferred 命中 → tag_score）
→ 语义相似度（BGE-M3 检索 semantic_query → vec_score）
→ 质量分（时长匹配槽位 min/max）
→ score = vec*0.50 + tag*0.30 + quality*0.20 − dup_penalty
→ Top 3-10 + 推荐原因（"语义相似度 0.51; 标签命中 客户家"）
```

## 5. CLI

```
--template-register        注册 CT01/CT02
--template-list            列出已注册
--template-recommend TID VER SLOT   槽位推荐（Top10）
--template-select PRJ TID SLOT SEG STATUS   保存选镜
```

## 6. 测试：32/32 pytest 通过

```
tests/test_p5_templates.py          4 passed  ← P5 新增（定义/注册/推荐/选镜）
tests/test_p4_search.py             4 passed
tests/test_p3_classification.py     5 passed
tests/test_p2_scene_asr_ocr.py      5 passed
tests/test_p11_lifecycle.py         8 passed
tests/test_p1_assets.py             4 passed
tests/test_p1_migrate.py            2 passed
```

## 7. 真实素材验证

| 项 | 结果 |
|---|---|
| 模板注册 | ✅ CT01（8 槽）+ CT02（9 槽）入库 |
| CT01 槽位 1 推荐 | ✅ 语义查询"小户型岛台强视觉"返回 3+ 候选（vec 0.51/0.49），带推荐原因 |
| 选镜保存 | ✅ project_segments 表（candidate/selected/backup/excluded） |

## 8. 遗留（写 BACKLOG）

- **CT01×3 / CT02×3 完整模板测试**（QA 阶段，需更多素材）
- **候选缩略图/时间戳展示**（P6 粗剪时补充）
- **avoid_tags 硬过滤**（当前实现支持，真实素材未触发）

## 9. Git

- 仓库：`yuhao8977-stack/treecut-v13`（公开）
- 新增：templates/definitions.py + templates/engine.py + tests/test_p5_templates.py
- main.py：--template-register/list/recommend/select

---

## 10. 结论

**P5 READY** —— CT01/CT02 模板驱动候选推荐真实可用。按总控指令继续 P6（人工选镜 + AI 排序 + FFmpeg 粗剪）。
