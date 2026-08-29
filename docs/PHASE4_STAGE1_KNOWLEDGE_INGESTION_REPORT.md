# PHASE4 STAGE1 — KNOWLEDGE INGESTION REPORT（Knowledge Foundation）

> 状态：**Stage 1 第一停点 —— 知识导入 + 审计 + 检索 + Business Cognition 最小链路完成**
> 日期：2026-08-29
> 纪律：未把知识库整份塞 Prompt / 未覆盖 L1-L2 / 未用知识反推视觉 / 未自动剪辑 / 未进 Stage2
> 源：`TreeCut_行业认知知识库_V1.0.xlsx`（主结构化）+ `.docx`（解释性辅助）

---

## 1-2. 知识导入概览

**186 条知识**（主表 01_知识主表）成功导入为 KnowledgeRecord（versioned/traceable/typed/retrievable）：

| 类型 | 条数 | 说明 |
|---|---|---|
| **FACT** | 78 | 稳定产品/行业事实（product/material/craft/scene 等已业务验证项） |
| **HYPOTHESIS** | 98 | 待数据验证（user_needs 14 / business_value 12 / shot 22 / content 等运营假设） |
| **PLATFORM_RULE** | 10 | 平台合规（TTL 30 天，动态） |
| **合计** | **186** | |

**按 namespace（13 个正式 namespace）**：product 16 · materials_styles 15 · craft_trust 7 · functions 25 · industry_taxonomy 23（场景+专业）· user_needs 14 · content_types 10 · content_roles 4 · shot_ontology 22 · semantic_mappings 10 · business_value_rules 12 · negative_rules 18 · platform_compliance 10

**按 confidence**：HIGH 127 / MEDIUM 58 / LOW 12（原 Excel 0.7-0.99 归一为五档；HYPOTHESIS 默认 DRAFT 非 ACTIVE）

## 3. Source Registry ✅

6 个来源登记（`knowledge/source_registry/source_registry.yaml`）：NKBA 专业机构（TTL 365）· 小红书公约/聚光/主题规范（TTL 30）· 业务人工验证（私有 HIGHEST）· Word 解释辅助。每个含 source_id/version/trust/scope/content_sha256。

## 4. Knowledge Audit ✅（knowledge/knowledge_audit.json）

| 项 | 结果 |
|---|---|
| duplicate knowledge_id | **NONE**（修复 content_role/professional 旧文件残留） |
| semantic duplicate | NONE |
| conflicts | **0** |
| 缺 source | **0** |
| **NEEDS_SOURCE** | **90**（business_value/content_types/negative/shot/user_needs/semantic_mappings/content_roles —— 需人工/外部来源确认） |
| 需人工确认项 | 116（HYPOTHESIS + NEEDS_SOURCE） |
| PLATFORM_RULE 缺 TTL | NONE（10 条全 30 天） |

## 5-8. 检索 + 认知

- **KnowledgeService**（`knowledge_service.py`）：get_by_id / search / search_by_namespace / semantic_search（SigLIP 文本编码）/ retrieve_for_evidence / retrieve_business_rules / retrieve_negative_rules / retrieve_templates / retrieve_user_needs —— **结构化过滤 + 语义重排双通道**
- **BusinessCognitionServiceV1**（`business_cognition_service.py`）：Evidence normalization → Knowledge retrieval → Rule matching → Negative filtering → Structured output → Traceability
- **EvidenceReference**：每字段带 reliability（people HIGH / component MEDIUM_HIGH / material LOW / **semantic_action VERY_LOW 强制**）
- **Negative Rules**：NR001-NR005（插座≠操作、工厂≠客户案例、弱材质≠高端、people≠家庭、semantic_action 不单独触发）

## 9-10. Validation

**Validation Set：43 条**（Cal333/Stage3/Mini，禁 Holdout）覆盖 10 类：抽屉收纳 123 池 / 伸缩 162 / 插座 115 / 人物 311 / 工厂 423 / 展示 115 / 工艺 32 / 多人 74 / 空间布局 3 / 弱证据 2。34/43 有 user_needs，14 有母题。

**核心测试：10/10 PASS**（TEST A-H + NR004/NR005）：
- A 抽屉+STORAGE→STORAGE ✅ · B 插座无动作→不推 OPERATE_SOCKET ✅ · C 伸缩→不推小户型 ✅
- D 工厂→不推客户案例 ✅ · E people→不推家庭聚会 ✅ · F 弱材质→不推高端断言 ✅
- G semantic_action→不当硬事实 ✅ · H 低证据→UNKNOWN ✅

## 11. Knowledge Snapshot ✅

**KNOWLEDGE_SNAPSHOT_V1.json**：23 知识文件 + 186 条 · **knowledge_snapshot_sha256 = `2111b0b33a873a4b3f26a302bc331e183788768d98deca3372af2a598a7ab9ce`**
schema：knowledge_record 1.0 / business_cognition 1.0 / template 1.0 · source_registry 1.0

---

## 23 问答复

1. **导入多少条？** → **186**（FACT 78 / HYPOTHESIS 98 / PLATFORM_RULE 10）
2. **类型分布？** → 78/98/10
3. **namespace？** → 13 个正式 namespace（product/materials_styles/craft_trust/functions/industry_taxonomy/user_needs/content_types/content_roles/shot_ontology/semantic_mappings/business_value_rules/negative_rules/platform_compliance）
4. **有可靠 source？** → 96（含业务词典+平台官方+专业机构）
5. **NEEDS_SOURCE？** → **90**（运营假设/生产规则类，待验证）
6. **duplicate？** → **0**（修复残留后）
7. **conflict？** → **0**
8. **Source Registry 完整？** → 是（6 源，hash+TTL+trust）
9. **Snapshot SHA256？** → **`2111b0b3…`**
10. **Business Cognition 最小链跑通？** → 是（43 条验证集，10/10 测试）
11. **Knowledge 反向污染视觉？** → **NO**（L1/L2 独立，negative rules 防）
12. **semantic_action 限制？** → VERY_LOW WEAK_EVIDENCE，不单独触发规则（NR005）
13. **user_need taxonomy？** → 是（14 条种子 + 引擎规则）
14. **business_value taxonomy？** → 是（12 条种子 + SEM 映射）
15. **Content Role 四分类？** → 是（TRAFFIC/SEARCH/TRUST/CONVERSION，primary+secondary）
16. **Mother Themes 五类？** → 是（SPACE_SOLUTION/FAMILY_SCENE/DECISION_AVOID_PIT/AESTHETIC_STYLE/CRAFT_TRUST，全 HYPOTHESIS）
17. **Shot Function 与 shot_role 分离？** → 是（Phase4 叙事功能 vs Phase3 视觉标签）
18. **Negative Rules 生效？** → 是（NR001-NR005，测试 PASS）
19. **检索双通道？** → 是（SQLite FTS 结构化 + SigLIP 语义重排）
20. **Validation Set？** → **43 条**（禁 Holdout）
21. **核心测试通过？** → **10/10**（A-H + NR004/005）
22. **仍需人工/外部验证？** → 90 NEEDS_SOURCE + 98 HYPOTHESIS（含尺寸标准/材料性能/平台规则时效）
23. **进入 STAGE2 条件？** → **部分具备**：知识结构/推理机制已建稳；**待补充知识库内容并入 + 90 NEEDS_SOURCE 评估后**再进 STAGE2（BUSINESS COGNITION HARDENING）

---

## 产物

- `knowledge/`（schemas ×3 + source + 13 namespace + source_registry + mother_themes/content_roles）
- `knowledge/knowledge_manifest.json` · `knowledge/knowledge_audit.json`
- `src/treecut/services/knowledge_service.py` · `business_cognition_service.py`
- `KNOWLEDGE_SNAPSHOT_V1.json`（DATA_ROOT）
- `KNOWLEDGE_BRAIN_STAGE1_VALIDATION_SET.json` + `_RESULTS.json`（DATA_ROOT）
- 本报告 `docs/PHASE4_STAGE1_KNOWLEDGE_INGESTION_REPORT.md`

## 第一停点

**STOP** —— 等待架构监工检查 + 你补充的知识库内容并入后，再进 Stage 2。
