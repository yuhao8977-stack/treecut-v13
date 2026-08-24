# AI 认知体系收尾优化报告（BRAIN OPTIMIZATION）

- **日期**：2026-08-24
- **范围**：A) 成片自动渲染；B) Phase 2b 视觉模型补齐（CLIP）
- **状态**：A 已验收（MP4 成片生成）；B 引擎已实现并单素材验证通过，批量后台运行

---

## A. 成片自动渲染

### 实现

`cognitive/production.py` 扩展：
```
生产计划(picks) → EditPlan(复用 workflow.EditSegment)
  → render_video_plan() → preview.mp4（MP4 成片）
  → build_jianying_draft() → 剪映草稿（需 narration/bgm/srt，自动生成静音占位）
```

### 验收

**命令**：`--brain-produce T003 产品介绍001`

| 项 | 结果 |
|---|---|
| MP4 成片 | ✅ `preview.mp4`（3.4 MB，竖屏 540×960） |
| 槽位素材 | 4/4（产品亮相/卖点拆解/细节特写/CTA） |
| 生产计划 | `production_plan.json` |
| 口播脚本 | `narration_script.txt` |
| 状态 | **rendered** |

**链路打通**：认知理解（内容类型）→ 模板匹配（T003）→ 自动选材 → **渲染成片**。设计文档 §4.5 的目标输出现在有了真实产物。

---

## B. Phase 2b 视觉模型补齐（CLIP）

### 背景

Phase 1 发现 **36% 素材无产品识别**（ASR 文本过短/无解说）。需要视觉模型补齐纯画面素材。

### 模型选型

| 候选 | 结论 |
|---|---|
| Florence-2 | ❌ 与 transformers 5.15 不兼容（custom config 缺 forced_bos_token_id，patch 破坏 StrictDataclass 验证） |
| **CLIP（vit-base-patch32）** | ✅ transformers 5.x 原生支持，580MB 已在 HF 缓存，无 custom code |

### 实现

`cognitive/vision.py`：CLIP 零样本分类（CPU float32）

**中文标签体系**（家具/岛台行业）：
| 组 | 标签示例 |
|---|---|
| scene | 客户家的厨房/工厂车间/家具展厅/安装施工现场… |
| product | 厨房岛台/岩板台面/实木餐桌/餐边柜… |
| material | 岩板纹理/大理石纹理/木纹饰面/黑色哑光台面… |
| function | 抽屉收纳/岛台伸缩/轨道插座/隐藏电器… |

**流程**：候选（reasons 无 products）→ 关键帧 → CLIP 分类 → 标签写回 content_classification.reasons + scene_semantics → 内容类型推断（客户家→客户案例等）

### 单素材验证

对素材 `000340d8` 的关键帧：
```
[scene] 家具展厅 0.23 | [scene] 安装施工现场 0.19
[material] 大理石纹理 0.195 | [material] 黑色哑光台面 0.189
[function] 展示产品细节 0.194
```
**识别准确**（该素材确实是展厅/安装场景）。

### 兼容性修复

- transformers 5.x `get_image_features` 返回 `BaseModelOutputWithPooling` → `_as_tensor()` 取 pooler_output
- 批量补认知后台运行中（`--brain-vision 10`）

---

## 验收结论

| 优化项 | 状态 |
|---|---|
| A: MP4 成片自动渲染 | ✅ preview.mp4 已生成 |
| A: 剪映草稿链路 | ✅ 接口接入（占位文件方案） |
| B: CLIP 视觉引擎 | ✅ 单素材验证通过 |
| B: 批量补认知 | 🔄 后台运行 |
| git 提交 | ✅ `0bc4d75` |

## 复现命令

```bash
# A: 成片渲染
python -m treecut.main --brain-produce T003 产品介绍001

# B: 视觉补认知
python -m treecut.main --brain-vision 10        # 批量
python -m treecut.main --brain-vision-status    # 可用性
```
