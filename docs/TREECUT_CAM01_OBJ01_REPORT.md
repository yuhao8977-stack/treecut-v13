# POST-A3 CAM01 OBJ01 — Semantic Object Box Anchor 报告（FAIL_OBJECT_BOX）

- 日期：2026-09-07 · main @ fbaa70e → 本次提交
- 确定性对象级 bbox 变换（无拟合/无特征）；验证工具修正独立实现；不读 A3；无动作判定

## 1. STRUCT01 验证工具修正（OBJ01 独立 utility；STRUCT01 历史未覆盖）
- `CAM01_STRUCT01_DEFECT_CHAMFER_DT_01` 修正：DT 语义 edge=0/背景≠0 → 输出"到最近 edge"距离。
- raw 距离：禁止 canonical×min(sx,sy)；预测/目标点真实映回 raw 帧后 Euclidean（forward 用 t1 raw、reverse 用 t0 raw）。
- 0 残差非缺失（is not None 判定，不吞 0）。
- 单元测试：chamfer DT 语义 / 各向异性 raw 映射精确 / 0 非缺失 / roundtrip（4 项，1 项容差修正后全过）。

## 2. 主结果（36 pairs）
| 指标 | 值 |
|---|---|
| validation eligible | 33/36（3 对结构不足） |
| ANISOTROPIC validated /36 | **0** |
| ISOTROPIC validated /36 | **0** |
| OBJECT_BOX_MULTI /36 | 0 |
| OBJECT_BOX_SINGLE /36 | 0 |
| OBJECT_BOX_CONFLICT /36 | 0 |
| OBJECT_BOX_NO_ANCHOR /36 | 36（33 验证未过 + 3 不足） |
| object-box union /36 | **0** |
| case coverage /9 | 0 |
| pooled sym median/P90/P95 | null |

- 残差画像：ANISO sym median 常见 1.9–8.6px（部分接近 3px 门），但 **P90 尾重 10–58px**（标注遮挡/入画变化/透视）→ 双双过门 0/36（P90≤8 为主杀）。
- bbox jitter：center 位移 median ≈35.6px（语义帧间大平移），w/h 比 ≈0.99 → bbox 中心平移大但尺寸近 1：框内可见主体内容变化（不同柜体段进出画面）不能被纯轴对齐仿射覆盖。

## 3. 困难案例
1641：3 对 INSUFFICIENT + 1 NO；10000/2543/21674：全 NO（验证未过）。无特判。

## 4. NEG target control
MULTI 0 · SINGLE 0（无 validated anchor；真实 contract）。

## 5. 判定（预置门槛）
- **FAIL_OBJECT_BOX**（union 0 < 17）→ **SEMANTIC_BOX_ANCHOR_NOT_SUFFICIENT = YES**。
- NEXT_BLOCKER = **HIGHER_LEVEL_DENSE_OBJECT_CORRESPONDENCE**（如 pretrained semantic/dense features 或 object-level tracker；不回低层 OpenCV）。不自动开始。
- Candidate：未冻结（frozen=false）。

## 6. 全链 Anchor 汇总（对照）
V24R1 12/36 · GFTT 17/36 · V26R1 7/36 · STRUCT01 0/36 · **OBJ01 object-box 0/36** →
单靠"已知岛台框"的对象级 bbox 坐标变换，在 3px/P90 8px 严格门下不足以承担本数据相机/对象归一（尾部结构不匹配为主因）。

## 产物
reports/storage/TREECUT_CAM01_OBJ01_CONFIG.json · _STRUCT01_CORRECTIONS.json · _METHOD_MATRIX.json ·
_STRUCTURAL_VALIDATION.json · _BBOX_JITTER.json · _TARGET_DIAGNOSTIC.json · _NEG_TARGET_CONTROL.json ·
_RESULT.json · _CANDIDATE.json · _GALLERY.html · scripts/posta3_cam01_obj01.py ·
tests/test_cam01_obj01_utils.py
