# STAGE8 G5 — Production QA + Dedup 报告

状态：**PASS(WITH_LIMITATIONS)**（分层实现 + V1/V2 负回归编码；限制见下）

## QA
- ProductionQAService 分层：TECHNICAL/SOURCE/SEMANTIC/PRODUCTION/HUMAN；P0 门禁（脏源/无支撑核心主张/错动作/错功能视觉/AV差/视频短于音频/新字幕缺失/重大重复）→ 禁 READY_FOR_HUMAN_REVIEW
- P0 键映射显式（AV_SYNC→AV_DURATION_MISMATCH 等）；WARNING 级记录债务不冒充 P0
- V1 负回归：脏源+无字幕+短视频+错配 → READY=False（测试）
- V2 负回归：字幕55(债务)/无BGM/SAPI/伸缩口播配插座/重复结尾/动作未演示 → READY=False（测试）；字幕小=WARNING 非 P0（不谎报）

## Dedup
- 级别：EXACT_SEGMENT/SOURCE_TIME_OVERLAP/SAME_ASSET/视觉pHash(≤6强/7-12复核)/叙事近重
- V2 时间线实测：11 处命中（含同案例/同角色薄抽人物镜重复风险），HIGH 级 → P0 MAJOR_DUPLICATE
- 限制：视觉 pHash 真实视频帧接入待 frame 缓存（当前叙事级已生效）；阈值按报告校准

## 输出
- TREECUT_PRODUCTION_QA_SCHEMA_V2 / QA_RULES_V2 / PILOT_V1_REGRESSION(测试) / PILOT_V2_REGRESSION(测试+运行) / PRODUCTION_DEDUP_POLICY_V1 / QA_FALSE_PASS_AUDIT_V1
