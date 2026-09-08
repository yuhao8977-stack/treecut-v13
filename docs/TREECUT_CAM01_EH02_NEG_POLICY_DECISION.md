# TREECUT CAM01 EH02 — NEG Policy Authority Freeze 决策文档

- **decision ID**: `EH02-NEG-POLICY-DECISION-001`
- **日期**: 2026-09-08
- **baseline SHA**: `c2bb7b655e1c8224ce3c4584dda6ca128a591a12`
- **性质**: 从本 commit 起 NEG_REFERENCE_CONTROL 相关政策的**唯一正式前向权威**。
- **适用范围**: CAM01 Evidence-Hierarchy router（EH01→EH02→后续）；NEG control 判定；
  未来 GEOM 准入的 reference 资格。
- **不适用**: 不改写 EH01/EH01R1/EH01M1/EH02 任何历史报告与结论（supersedes 仅限政策表述）。

## 1. 政策条款（17 条，冻结）

1. **REFERENCE_STRONG 语义**：表示该 pair 有可靠的 reference transform/evidence，**不代表**
   是正向伸缩动作（EXTEND/RETRACT/STATIC 是动作判定，不在本政策内）。
2. **Router role-blind**：POS/NEG、NO_ACTION、target truth **不得作为路由输入**；role 只在
   router 冻结后的 readiness diagnostic 读取。
3. **NEG strong 允许存在**：NEG pair 可以合法成为 REFERENCE_STRONG。
4. **NEG_REFERENCE_CONTROL_PRESENT**：至少 1 个 role=NEG、target-valid、REFERENCE_STRONG
   的独立样本。
5. **NEG_REFERENCE_CONTROL_ESTABLISHED**：至少 **3 个不同视觉内容 family** 的 NEG 样本；
   每个样本必须同时满足 target-valid、REFERENCE_STRONG、且经过 **frame/ROI 级人工复核**。
6. **视觉内容 family（visual content family）**：样本多样性维度——不同源视频、场景、物体
   构成、拍摄方式或动作干扰类型。
7. **算法证据 family（algorithmic evidence family）**：方法来源维度——GFTT / V24 / DENSE /
   GLOBAL 等。
8. **算法不能冒充视觉 family**：三种算法验证同一个视觉样本，不得算作 3 个视觉 family。
9. **V24 与 GFTT 同属 FEATURE_LOCAL 证据链**，不重复计算为独立算法佐证。
10. **2543 1.202→1.717**：允许作为**第一个 NEG strong target-valid**；
    NEG control PRESENT=YES；当前只计 **1 个视觉内容 family**。
11. **9697 1.236→2.885**：虽为 NEG REFERENCE_STRONG，但 **target-invalid**；不得计入
    NEG control。
12. **21674 1.201→2.803 与 9697 1.236→2.885（target-invalid strong）**：可保留
    transform-quality 判级；必须显式 `target_eligible=false`；不得进入 target-level
    readiness、NEG control 或 GEOM 训练。
13. **≥3 family 只代表 ESTABLISHED**；不自动批准 GEOM。
14. **即使 ESTABLISHED 达成**，进入 GEOM 仍需单独规格、验收门和用户批准。
15. **SECTION_31_SOURCE_STATUS = NOT_FOUND**：原始 §31 指令不在仓库，保持 NOT_FOUND，
    不伪造历史来源。
16. **本决策文档为新的前向权威**：`NEG_STRONG_POLICY_AUTHORITY =
    RESOLVED_BY_EH02_NEG_POLICY_DECISION`。
17. **不回写/篡改旧 EH01/EH02 历史结论**。

## 2. 明确允许 / 禁止

- 允许：NEG strong 存在；2543 作为 PRESENT 计数；target-invalid strong 保留
  transform-quality 判级（显式 target_eligible=false）。
- 禁止：把 9697 / 21674 计入 NEG control；把算法证据 family 当视觉 family 计数；
  因 ≥3 family 自动进入 GEOM；在 GEOM 规格与用户批准前使用任何 NEG strong。

## 3. supersedes / does-not-supersede

- **supersedes**: 此前对话中任何将 "NEG_STRONG_REFERENCE 必须 = 0" 或 "≥3 family 即
  ESTABLISHED 可进 GEOM" 的非正式表述（政策层面）。
- **does-not-supersede**: EH01/EH01R1/EH01M1/EH02 报告中的历史结果数字；METHOD_MATRIX
  等 truth；router 实现规则（S1/S2/S3 仍由 ROUTER_FREEZE.json 定义）。

## 4. 文档完整性

- 本文件 SHA-256 见提交记录（`git log` 后 `git hash-object` 校验）。
- **后续更改必须通过新的决策文档**，不得静默修改本政策。

## 5. 与 V2 审计的关系

- 本决策关闭 V2 审计的 P0 风险（政策权威缺失）：NEG_STRONG_POLICY_AUTHORITY 由
  UNRESOLVED → `RESOLVED_BY_EH02_NEG_POLICY_DECISION`。
- V2/V2.1 交接文件中的 NEG 政策描述以本文档为准。
