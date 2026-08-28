# Phase 3 Stage 1 — Final Reconciliation（最终收口审计）

- **日期**：2026-08-28 ｜ 判定：`PASS WITH RECONCILIATION REQUIRED`
- **性质**：只读/数据重建收口；未修改模型 / AI 规则 / 融合权重；未学习 / Fine-tune / Fresh Holdout / Phase 4 / 行业知识库

## 1. 唯一 Segment 总数（核心问题）—— 严格 = 360 ✅

```text
ORIGINAL_SET  = 300 unique segment
TARGETED_SET  = 60  unique segment
ORIGINAL ∩ TARGETED = 0（实测）
MASTER_UNION  = COUNT(DISTINCT segment_id) = 360（实测 canonical is_current=1 恰 360 行且唯一）
```

## 2. 最终互斥集合（基于 segment_id 集合重算）

| 集合 | 数量 | 构成 |
|---|---|---|
| **ELIGIBLE** | **333** | 240（原 V1）+ 33（V3 resolved）+ 60（Targeted） |
| **NEEDS_REVIEW** | **1** | `09f514b80e394bdab5ef7cd25d6909b6`（NEEDS_ADJUDICATION + NEEDS_SECOND_REVIEW） |
| **EXCLUDED** | **26** | 24 boundary_unusable + 2 source=EXCLUDED（b3757ee9/e78ac11c） |
| **合计** | **360** | ✅ 333 + 1 + 26 = 360 |

- 三集合互斥实测：`E∩N=0、E∩X=0、N∩X=0`；`并集=360` ✅

## 3. 361 矛盾根因（如实说明）

**根因 = 集合归类 bug + 报告手写口径混用，二选一叠加**：

1. 上一版 `phase3_corpus_v2.py` 把 `truth_source=NEEDS_ADJUDICATION` 的 `09f514b8…` 错误归入 **excluded**（reason=`source=NEEDS_ADJUDICATION`）→ 脚本内部自洽为 `333 + 0 + 27 = 360`（**excluded=27、needs=0**）；
2. Master 报告手写 `needs_review=1 + excluded=27` → 拼出 **361**（把"正确 needs=1"与"错误 excluded=27"混用）。

**修正**：`NEEDS_ADJUDICATION` 属"待裁决"（needs_review），不属于"排除"；`09f514b8…` 唯一，无重复计入 eligible/needs/excluded。修正后 **333 + 1 + 26 = 360**，与架构监工推算完全一致。

## 4. CALIBRATION_CORPUS_V2 最终真实数量

- **eligible_unique = 333**（唯一性校验通过：333 段、0 重复）
- Manifest 已重建（revision `rec-v1`）：`CALIBRATION_CORPUS_V2_MANIFEST.json`
- **sha256 = `aa6c2a8d45777165`**（文件级校验）
- counts：`unique_total=360, eligible=333, needs_review=1, excluded=26`

## 5. COVERAGE_MATRIX_V3 是否需要变化

- **不需变化**：eligible 仍为 333（集合修正只移动了 09f514b8 从 excluded→needs，不涉 eligible）
- 已按修正后 eligible 重新生成确认：**GOOD 23 / MEDIUM 2 / LOW 16 / EMPTY 0**（41 组合）——与上一版一致
- `COVERAGE_MATRIX_V3.json`（revision `rec-v1`）

## 6. "98% 工厂"措辞修正（重要）

**证据核查**：`semantic_annotations` 仅覆盖 300/41814 段；`assets`/`segments` 表**无 scene 列** → **全素材库（22465 asset / 41814 segment）不存在任何可靠的场景审计**。

**正式修正**：
- ✅ 可证明：**CALIBRATION_CORPUS_V2 中 FACTORY = 327/333 ≈ 98.2%**（Calibration 分布）
- ❌ 不可证明："整个素材库 98%+ 是工厂"（Library 分布）
- 结论：**CALIBRATION_DISTRIBUTION ≠ LIBRARY_DISTRIBUTION**。全素材库真实场景比例尚未由可靠人工/视觉认知审计，后续 Stage 2 视觉模型全库跑通前不得外推。

## 7. Playback 历史根因证据等级（降级）

- 当前修复后行为（保留）：单击=1、连点=1、800ms 后再点=2、load100 后单击=1 ✅
- **旧版本多 launch 精确事件链未独立捕获**（无"一次物理点击 → _play_full 进入 N 次"的旧版 instrumentation/日志）
- 因此"多个重叠按钮一次点击命中多个 handler"**不是 CONFIRMED ROOT CAUSE**，降级为：
  > **LIKELY CONTRIBUTING CAUSE**：旧 UI 重复构建（已确认）与播放入口异常高度相关；旧版多 launch 精确事件链未单独捕获；当前已通过 唯一 UI + PlaybackController + Single-flight/Debounce 可靠治理。

## 8. Standalone vs Main Review 代码复用审计

| 组件 | Standalone（phase3_review_ui.py） | Main（review_center.py） | 共享？ |
|---|---|---|---|
| `_V21Form`（V2.1 表单） | 定义 | import 复用 | ✅ 共享 |
| `validate_v21` | 定义 | import 复用 | ✅ 共享 |
| `PlaybackController` | 定义 | import 复用 | ✅ 共享 |
| Schema V2.1 / cn/en / GROUPS | 定义 | import 复用 | ✅ 共享 |
| **`_persist`（保存 SQL）** | 2 份（V3/Targeted） | **1 份（ReviewTaskWindow 自写）** | ⚠️ **3 处重复实现** |

**风险**：保存 SQL 3 处重复 → 未来字段变更可能漂移（一处改一处漏）。**本阶段不重构**（仅报告）；建议 Stage 2 将保存逻辑收敛到 `AnnotationService` 单一入口。

## 9. Human Confidence 口径

- V3 34 条 = 全 MEDIUM；Targeted 60 条 = 全 MEDIUM + REVIEWED
- 结论：`human_confidence` 当前 **NOT_CALIBRATED / NO_EMPIRICAL_STRATIFICATION**（无分层统计价值）
- **Stage 2 禁止按 HIGH/MEDIUM/LOW 自动赋训练权重**；字段保留供未来积累；不要求重审 94 条

## 10. 九问总结

1. 总 unique segment 是否严格 = 360？ → **是**（实测 360，唯一）
2. eligible / needs / excluded 最终？ → **333 / 1 / 26**
3. 361 矛盾根因？ → 脚本把 NEEDS_ADJUDICATION 误归 excluded（27）+ 报告手写 needs=1 混用口径；修正后 360
4. Calibration Corpus V2 真实数量？ → **333**（sha256 `aa6c2a8d45777165`）
5. Coverage V3 需变化？ → **否**（eligible 不变；重算确认 GOOD 23/LOW 16/MEDIUM 2）
6. "98% 工厂"应描述？ → **Calibration（327/333）**；全库分布未审计，禁止外推
7. Playback 历史根因证据等级？ → **LIKELY CONTRIBUTING CAUSE**（非 confirmed；当前已治理）
8. Standalone/Main 共享核心逻辑？ → **共享**（表单/校验/播放/词典）；`_persist` 有 3 处重复（风险已报告，暂不重构）
9. Stage 1 是否满足进入 Stage 2 条件？ → **数据口径已收干净、UI/播放/接入已验收、121 测试通过 → 满足**；最终 FULL PASS 待架构监工确认

## 交付物

- `docs/PHASE3_STAGE1_FINAL_RECONCILIATION.md`（本报告）
- `CALIBRATION_CORPUS_V2_MANIFEST.json`（rec-v1，sha256 `aa6c2a8d45777165`）
- `COVERAGE_MATRIX_V3.json`（rec-v1）

> **完成后停止**：未进入 Stage 2、未创建 Fresh Holdout、未修改模型/规则、未自动学习。等待架构监工最终确认（FULL PASS）后再进入 Stage 2（RTX 3050 + 静态视觉/时序动作模型，重点 material/product_variant/shot_role/action）。
