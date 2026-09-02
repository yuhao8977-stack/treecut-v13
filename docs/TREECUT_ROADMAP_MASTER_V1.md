# TreeCut 主路线图（唯一主进度宪章）V1

> 冻结日期：本文档建立后即为主项目唯一进度来源。
> 编号规则：**正式主线 = Stage0～Stage10**；V0.x / PHASE 等仅作历史实施记录保留，不再作为最高层主进度。

## 1. 当前正式状态

```
STAGE8_PRODUCTION_QUALITY_HARDENING
```

- 第一条真实 Pilot：`B007_FIRST_REAL_PILOT_V1` = **HUMAN_REJECTED**（技术 Production Path PASS / 内容 Production Quality FAIL）
- 第一条修正 Pilot：`B007_FIRST_REAL_PILOT_V2` = **READY_WITH_LIMITATIONS（待人工对比）**
- Stage8 不设直接 PASS，必须依次通过 G1→G6。

## 2. 主阶段表（唯一仪表盘）

| 主线 | 状态 | 说明 / 后续动作 |
| --- | --- | --- |
| Stage0 Architecture | ✅ PASS | Git/DB/存储/Truth/模块治理 |
| Stage1 Asset | ✅ PASS | Canonical Asset、媒体身份、存储 |
| Stage2 Segment | 🟡 | 基础 PASS；动作切点待 G2 提升 |
| Stage3 ASR/OCR/Asset Type | 🟡 | ASR/OCR 成熟；raw/finished 分类未成硬闸 → **G1 补强** |
| Stage4 Semantic Labels | 🟡 | Scene/Product/Function/Qwen/L3 已有；持续校准 |
| Stage5 Dedup | 🟡 | Exact SHA 成熟；Near Duplicate 不足（Production 阶段顺补） |
| Stage6 Retrieval | 🟡 | 自动召回可用；质量不足 → **G3 补强** |
| Stage7 Template | 🟡 | DNA+Template Candidates 出现；未过真实成片验证 → G3 后验证 |
| **Stage8 Production** | 🔴 当前主战场 | **约 3～6 个有效开发日**（G1→G6） |
| Stage9 Template Expansion | ⏳ | 约 1～2 周渐进（Stage8 PASS 前禁止） |
| Stage10 Feedback Loop | ⏳ | 随发布持续 |

## 3. Stage8 修复闸门（顺序执行，逐门验收）

```
G1 PRODUCTION SOURCE GATE       ← 当前待执行
G2 ACTION / SUBCLIP GATE
G3 CLAIM → VISUAL / STORY GATE
G4 AUDIO / CAPTION / BGM / AV SYNC GATE
G5 PRODUCTION QA GATE
G6 PILOT VALIDATION GATE
```

不通过当前 Gate 不得进入下一 Gate；任一 Gate 验收不通过回到对应 Gate 修复，不推 Pilot3 掩盖问题。

## 4. 能力债务（对应旧 L 层）

| 能力层 | 债务 | 归属 Gate |
| --- | --- | --- |
| L3 Asset Type（成片/原片） | Published 成片曾混入生产源 → **P0** | G1 |
| L6 Motion / Action | 有标签 ≠ 看到动作 | G2 |
| L8 Function Demonstration | 能判功能存在，不能判完整演示 | G2/G3 |
| L11 Template Relevance | 自动选镜不可靠 | G3/G5 |
| L12 Human Feedback | 仅 1 条 HUMAN_REJECTED | G5/G6 |

约束：**不得通过新建另一套平行系统解决**，必须在现有 Canonical 体系（asset / segment / semantic annotation / human annotation / script beat / shot candidate / production / feedback）内增量修正。

## 5. 最终产品目标（冻结）

```
TreeCut Production V1

INPUT   : topic / script
SYSTEM  : script understanding → beat parsing → automatic retrieval
          → automatic subclip selection → automatic ordering
          → narration → subtitle → BGM → timeline → render → QA
OUTPUT  : 3 条候选成片
HUMAN   : 看片 → 接受/拒绝/局部换镜 → 人工确认后发布

禁止：以“人工逐槽位选所有镜头”作为最终常态流程
禁止：AutoPublish 作为当前目标
```

## 6. Stage8 PASS 标准（冻结）

1. 先完成 Pilot V2 人工对比；
2. 再执行 Pilot2～Pilot5（内容类型覆盖：功能演示 / 真实客户案例 / 尺寸避坑 / 收纳空间解决 / 工艺产品信任）；
3. **至少 4/5 达到 BASICALLY_PUBLISHABLE**：
   - 定义 = 无需开发者修改代码；只允许运营级人工微调（换一个镜头 / 调一句字幕 / 微调 BGM / 从 3 条候选中选 1 条）；
   - 不是“任何人工修改都不需要”，而是“不需要每次回来修算法”。
4. 满足 → `STAGE8_PASS` → 才可进入 Stage9；否则保持 `STAGE8_NEEDS_REPAIR`。

## 7. 禁止事项（Stage8 PASS 之前）

- 全面扩展 T03～T12 模板
- 大规模账号扩样本
- AutoPublish
- 无关 UI 重构
- 大型模型替换

## 8. Stage9 扩展批次（PASS 后）

Batch A: T01/T02/T03/T05 → PASS → Batch B: T04/T06/T07/T11 → PASS → Batch C: T08/T09/T10/T12

## 9. Stage10 反馈闭环（重定义）

已有强历史 Creator/Paid 数据；真正缺的是生产侧串联：
`production_id → template → script → segments → published note → Creator result → Paid result → Human feedback`
分析方向（仅关联分析，不宣称因果）：
- 什么镜头更常被接受？哪类镜头常被换掉？哪些模板稳定生产？哪些结构近期表现更稳？

## 10. 状态记录位置

- 本文档：唯一主路线图（人工维护，随 Gate 验收更新）
- `reports/storage/TREECUT_PROJECT_STATE_V1.json`：机器可读当前状态快照（Gate 进度）
