
## 晨间勘误（2026-09-03 10:09:37）— 校准口径与状态冻结（架构师裁定）

- **校准口径纠正**：G2 校准目标 = 80–120 **Segment/资产级**独立样本。当前真值：segment/asset 级 ≈ **20**，未达标；132 时序帧为 **TEMPORAL_EVIDENCE**（同一样本看得更细），**不等价 132 独立样本**。凡此前表述"帧级132满足80-120指导"一律作废（本文件与相关产物已改）。
- 校准扩充计划（cheap signals 先行，qwen 仅难例/人审子集）已写入 `TREECUT_G2_SEGMENT_CALIBRATION_STATUS_V2.json`。
- **状态矩阵冻结（架构师）**：G1=PASS ｜ G2/G3=ENGINEERING_READY_FOR_HUMAN_VALIDATION ｜ Dedup/G5=PROVISIONAL_PASS ｜ UI=USABLE_V1 ｜ VOICE=READY_FOR_INPUT ｜ BGM=LIBRARY_NOT_READY ｜ Regression=354/2/0
- 晨间人审包：`TREECUT_G2_HUMAN_REVIEW_V2.html`(20 queries×Top3+best+complete+boundary)、`TREECUT_G3_HUMAN_REVIEW_V2.html`(16 beats)、`TREECUT_DEDUP_HUMAN_REVIEW_V1.html`(真实 V2 镜头 4 对)；标记可导出 JSON（追加式，不动机器证据）。
- **G2 人审阶段门槛（第一阶段生产可用，非普适真理）**：已知硬负拒绝 100% / Top3 含可用动作 ≥85% / Top1 可用 ≥70% / 边界可用 ≥80%；分母=确实存在目标动作素材的 Query；无素材=NO_VALID_SOURCE_AVAILABLE，不算算法失败。
- **G3 门槛**：P0 核心主张错配 0 / Top3 含合适 ≥90% / Top1 合适 ≥80% / 无支撑核心主张通过 0 / 严重 SINGLE_CASE 故事冲突 0。
