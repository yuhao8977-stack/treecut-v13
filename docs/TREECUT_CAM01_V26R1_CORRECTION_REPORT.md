# POST-A3 CAM01 V2.6 R1 — Canonical Pair Support 修正报告（FAIL → 路线关闭）

- 日期：2026-09-07 · main @ d2f9faa → 本次提交
- 只修两个确定性缺陷；不调参/不碰 A3/无新人工；V2.6 历史保留为 superseded-pending-R1

## 1. 修复
- `CAM01_V26_DEFECT_CANONICAL_CELL_01`：t1 clean 曾误用 t0 像素矩形 → 真 canonical 512 平面：
  每帧 ISLAND_BODY − DYNAMIC union → crop→NN 512 binary → common=AND；6×6 cell 与 common_clean_px 全在 canonical 计算；
  source GFTT 仍从真实 t0 帧（canonical cell→t0 rect + t0 动态像素挖除）提取，不做 resize 后 LK。
- `CAM01_V26_DEFECT_NEG_CONTROL_PLACEHOLDER_02`：NEG target control 改为真实 pick_target 严格 contract（非占位 0）。
- 单元测试 6 项过（A：两帧不同 ib 时 rc0≠rc1 且用各自 ib；B：同 normalized 前景→canonical mask 相等；
  C：平移后全 clean cell common px 不减；D：CANON=512 真参与；+ union-overlap 2 项）。

## 2. 结果（36 island-present pairs）
| 指标 | V2.6(old,缺陷) | V2.6R1(canonical 修正) |
|---|---|---|
| common-clean availability | 34/36 | **36/36**（canonical 对齐全面成功） |
| avg candidate regions/pair | 4.94 | 5.11 |
| validated region instances | 31 | 31 |
| PAIR_REGION_MULTI /36 | 2 | **2** |
| PAIR_REGION_SINGLE /36 | 5 | 5 |
| PAIR_REGION_CONFLICT /36 | 6 | 6 |
| PAIR_REGION_NO_ANCHOR /36 | 23 | 23 |
| region union /36 | 7 | **7** |
| case coverage /9 | 3 | 3（multi 1/9） |
| pooled median/P90/P95 | 0.436/1.774/3.317 | 0.436/1.774/3.317 |

- 结论：canonical bug 影响的是"可用性数字的干净度"（34→36），**union 7/36 与 FAIL 并非 canonical bug 造成**；
  真正限制仍是：动态前景挖除后 6×6 cell 内可提特征太少（多数过不了 strict 2-fold）。

## 3. 困难案例（真实矩阵）
1641：4 对 NO（候选 3–5）；10000：1 CONFLICT+3 NO；2543：4 对 NO（候选 4）；21674：4 对 NO（候选 2–5）。无特判。

## 4. NEG target control（真实计算）
MULTI：0 case/pair；SINGLE：0 case/pair（computed=true，非占位）。不设 EXTEND threshold。

## 5. 判定（预置门槛，未改）
- improvement class = **FAIL**；PATCH_GRID_ROUTE_CLOSED = **TRUE**（union 7 < 20）。
- **NEXT_BLOCKER = STRUCTURAL_OBJECT_ANCHOR_V1**（正式；不做 V2.7 grid 调整）。

## 6. 保留观察
- canonical 修正本身验证成功：pair 级 clean 支持"可用性"100%（36/36）——该 representation 前提成立；
  瓶颈在 cleaned region 的特征密度与 2-fold 严格门，网格/patch 层面的"像素抠除"不足以提供稳定 transform 证据
  → 结构性/对象级（柜体轮廓/长边/角点/侧板框架线）是下一步唯一明确方向（按预置规则，不无限磨 grid）。

## 产物
reports/storage/TREECUT_CAM01_V26R1_METHOD_CORRECTION.json · _CANONICAL_SUPPORT.json · _REGION_METHOD_MATRIX.json ·
_REGION_CONSENSUS.json · _NEG_TARGET_CONTROL.json · _RESULT.json · _PAIR_REGION_GALLERY.html ·
scripts/posta3_cam01_v26r1.py · tests/test_cam01_v26_canonical.py
