# VISION_MODEL_BUNDLE_V2

> bundle_id: VISION_MODEL_BUNDLE_V2 · created: 2026-08-29 11:01 · git: 813fc5aa578dee55ba0cac8c61d5092859bd555a
> bundle_lock_sha256: `a87d31246066bf8c6b0b1410d7e0b3598d626dfd2163274de5b1a77ef3871852`
> stage3_dev_snapshot_hash: `59b6d52777a5ec7f37094953860b32f05bae2e3bb9f8a866a802d8c015932e29`

## 9 字段状态

| 字段 | 状态 | Primary | Fallback | Policy | DEV metric |
|---|---|---|---|---|---|
| people_presence | READY | PeoplePresenceAnalyzerV2 | SigLIP ONLY on technical failure | — | combined F1 94.2 / bacc 86.4（threshold 0.70 冻结） |
| product_family | READY/LIMITED_READY | StaticVisionAnalyzerV2 | — | single top-1 | Cal333 52.7% / Stage3 72.7% |
| component | READY_CANDIDATE | StaticVisionAnalyzerV2 | — | V2（Top3+gap0.10+min0.02） | Cal+Stage3 microF1 35.9 / macroF1 53.2 |
| function | READY_CANDIDATE | StaticVisionAnalyzerV2 | — | V2（Top3+gap0.10+min0.02） | Cal+Stage3 microF1 33.2 / macroF1 52.6 |
| scene_family | LIMITED | StaticVisionAnalyzerV2 | — | single top-1 | FACTORY 极度偏科 |
| material | EXPERIMENTAL/FALLBACK | StaticVisionAnalyzerV2 | — | V1（threshold 0.06）—— V2 已证退化 | Cal+Stage3 F1 22.2（MIXED/弱） |
| shot_role | EXPERIMENTAL | StaticVisionAnalyzerV2 | — | V1（threshold 0.06）—— V3 压缩未达门槛 | F1 36.9 / pred_avg 7.0 |
| product_variant | LIMITED | StaticVisionAnalyzerV2 | — | conservative top-1 | EXTENDABLE 有证据 |
| semantic_action | EXPERIMENTAL | SemanticActionRouterV2（per-action best-known） | — | — | 见 per-action map |

## SemanticActionRouterV2 per-action

- OPEN_DRAWER: V1_RULE（V1 优于 V2（P100））
- PULL_OUT: V1_RULE_SIMPLE（V1/V2 相近，用简单稳定路线）
- CLOSE_DRAWER: V2_STATE_EXPERIMENTAL（V2 提供非零能力）
- CLOSE_CABINET: V2_STATE_EXPERIMENTAL（V2 真实增益）
- OPEN_CABINET: NO_CLAIM（不得声称已有能力）
- RETRACT: NO_CLAIM（不得声称已有能力）
- OPERATE_SOCKET: INSUFFICIENT_SAMPLE（）
- OPEN_SINK_COVER: INSUFFICIENT_SAMPLE（）
- PERSON_SPEAKING: MOTION_BASELINE（motion evidence 仅）
- STATIC_DISPLAY: MOTION_BASELINE（）
- OTHER: DEFAULT（）

## 冻结纪律
- Bundle V2 = 每字段 best-known frozen route 不可变组合；LIMITED/EXPERIMENTAL 允许
- Fresh Holdout V1 仅 KNOWN BENCHMARK 参考，不用于 V2 选择
- 冻结后建立 FRESH_HOLDOUT_V2；禁止先看 V2 题再改 Bundle