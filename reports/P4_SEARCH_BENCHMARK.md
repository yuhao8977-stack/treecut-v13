# P4 报告：混合检索系统（FTS5 + BGE-M3/FAISS + 标签 + 质量 + 去重）

> 日期：2026-08-19 | 阶段：P4（第二阶段）
> 结论：**P4 READY**（28/28 pytest + 真实素材检索验证通过）

---

## 1. 目标回顾

构建统一混合检索：SQLite FTS5 全文 + BGE-M3/FAISS 向量 + 标签匹配 + 画质 + 去重惩罚。**复用已验证的 BGE-M3 + FAISS**（不换模型），支持自然语言运营查询。

## 2. 新增模块

| 模块 | 功能 |
|---|---|
| `search/embedding.py` | BGE-M3 文本嵌入（离线 HF 缓存 + 用户级缓存回退）+ FAISS IndexFlatIP（中文路径兼容写入/读取） |
| `search/hybrid.py` | 混合检索：FTS5(trigram 中文分词) + FAISS + 标签/质量/去重加权 |
| `analysis/embedding_worker.py` | 为 segment 生成 embedding（transcript+OCR+标签拼接）并建索引，接入生命周期 |

## 3. 检索流程

```
Query → FTS5(trigram) + FAISS Recall
      → 候选汇总(asset级)
      → 硬过滤(asset_type 等)
      → 标签匹配(tag_score) + 画质(quality_score) + 去重惩罚(dup_penalty)
      → score = vec*0.50 + tag*0.25 + quality*0.15 + text*0.10 − dup_penalty
      → Top K
```

## 4. CLI

```
--index-text         重建 FTS5 全文索引（transcripts/ocr）
--embed COUNT        为素材生成 segment embedding + FAISS 索引
--embed-status       向量索引状态
--search QUERY       混合检索（--search-topk N）
```

## 5. 测试：28/28 pytest 通过

```
tests/test_p4_search.py            4 passed  ← P4 新增（BGE-M3编码/FAISS建索引检索/FTS5中文/混合检索）
tests/test_p3_classification.py    5 passed  ← P3 回归
tests/test_p2_scene_asr_ocr.py     5 passed  ← P2 回归
tests/test_p11_lifecycle.py        8 passed  ← P1.1 回归
tests/test_p1_assets.py            4 passed  ← P1 回归
tests/test_p1_migrate.py           2 passed  ← P1 回归
```

## 6. 真实素材验证（2 个真实成片，43 segments）

| 项 | 结果 |
|---|---|
| FTS5 全文索引 | ✅ 343 条（transcript + OCR） |
| BGE-M3 嵌入 | ✅ 43 segments，dim 1024，33.7s |
| FAISS 索引 | ✅ ntotal:43（IndexFlatIP cosine） |
| 真实查询 "岛台 收纳 插座" | ✅ 返回 2 个真实成片，vec_score 0.60/0.54（语义相关），排序正确 |

## 7. 修复的 bug

1. **faiss.write_index/read_index 中文路径打不开**（C++ 层不处理 UTF-8）→ 临时 ASCII 目录写入/读取后移动
2. **FTS5 中文分词**（unicode61 把"伸缩岛台"当一个 token）→ trigram 分词器 + <3 字符 LIKE 兜底
3. **embedding 失败仍 mark_done** → 先 build_index 成功再 mark_done

## 8. 遗留（写 BACKLOG）

- **搜索 Benchmark**：30-50 条真实运营 Query（QA 阶段建立，需更多素材支撑）
- **segment 级结果展示**：当前返回 asset 级，UI 需要 segment 级（缩略图/时间戳）
- **embedding 增量更新**：新素材嵌入后全量重建（当前 force=True 全量，P4.1 可增量）

## 9. Git

- 仓库：`yuhao8977-stack/treecut-v13`（公开）
- 新增：search/embedding.py + search/hybrid.py + analysis/embedding_worker.py + tests/test_p4_search.py
- main.py：--embed/--embed-status/--index-text/--search

---

## 10. 结论

**P4 READY** —— 混合检索真实可用（BGE-M3 语义匹配真实成片）。按总控指令继续 P5（CT01/CT02 模板引擎）。
