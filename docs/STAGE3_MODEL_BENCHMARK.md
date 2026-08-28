# Stage 3 Model Benchmark（第一停点）

- **日期**：2026-08-28 18:44 ｜ 基线：VISION_MODEL_BUNDLE_V1_1（SigLIP base，EN prompt）

## People V2 诊断（STEP 3，CANDIDATE）

Fresh 30 people 成绩 0% 的**直接根因**：routing 回退 legacy（旧方案对未审段无输出 → 全 UNKNOWN）。
SigLIP raw（未回退时）在 Holdout30：acc 23.3%（cov 63.3%，YES recall 21%）。
→ 修复方向：People V2 **直接采用 SigLIP raw 输出**（不再 fallback legacy），并 benchmark 轻量 person detector（下一步）。

## Scene / Material / Variant / Semantic Action（CANDIDATE）

- Scene V2：multi-frame 聚合已启用（5 帧均值）；Fresh 24.1%（dev 37.9）gap 分析见 STAGE3_STAGE1 报告；balanced slice 需素材（非工厂极少 → INSUFFICIENT_SAMPLE）
- Material V2：global+crop/texture 证据链 CANDIDATE（素材长尾 INSUFFICIENT：实木等 support<5）
- Product Variant：联合 Static+Temporal+ASR 判断 CANDIDATE
- Semantic Action：Object+Motion+Fusion（DRAWER+外拉→OPEN_DRAWER 等）CANDIDATE；本轮确认 Farneback 仅为 motion evidence

## 约束

- 所有 Stage3 结果必须与 V1_1 比较（STAGE2_BASELINE_SNAPSHOT.json）
- product_family 不得退化（V1_1 Fresh 51.7% 为回归锚点）
- 模型更换须真实下载/加载/GPU 推理（禁凭排行换）
