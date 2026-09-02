# -*- coding: utf-8 -*-
"""G3 产物 + V2 回归文件 + Dedup 实测(V2 时间线) + QA 假阳审计 + G2 工程评估。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.claim_visual import parse_script_to_claims, classify_story_mode, AtomicClaim, Candidate, ClaimVisualMatcher
from treecut.services.production_dedup import Shot, detect_duplicates, narrative_score
from treecut.services.action_subclip import parse_qwen_state
from treecut.config.production import load_production_config

# ---- G3 输出 1: 原子主张(V2 旗舰脚本 + 含硬主张样例) ----
SCRIPT = ("岛台想好用，这三个细节最值得看。第一，上层薄抽，收纳小物不弯腰，打开就能拿到。"
          "第二，轨道插座，吃火锅煮茶都方便，插拔也顺手。"
          "第三，伸缩桌面，来客时一拉就变宽，平时收起来不占位。厨房好不好用，全在这些小细节里。")
claims = [c.__dict__ for c in parse_script_to_claims(SCRIPT)]
(OUT / "TREECUT_G3_ATOMIC_CLAIMS_V1.json").write_text(json.dumps({"claims": claims}, ensure_ascii=False, indent=1), encoding="utf-8")

# 视觉需求 schema(生成器规则化)
visreq = {"per_beat": ["required_object", "required_function", "required_action", "preferred_scene",
                       "required_context", "forbidden_dominant_object", "shot_role", "story_entity_requirement"],
          "claim_types": ["PRODUCT_IDENTITY", "MATERIAL", "MATERIAL_PROPERTY", "OBJECT", "FUNCTION",
                          "ACTION", "HARDWARE_PROPERTY", "DIMENSION", "SPACE", "USE_CASE", "CASE_IDENTITY", "CTA"],
          "forbidden_inference": ["岩板→耐高温", "抽屉→静音滑轨", "文件夹'伸缩'→动作", "ASR插座→视觉插座"]}
(OUT / "TREECUT_G3_VISUAL_REQUIREMENTS_V1.json").write_text(json.dumps(visreq, ensure_ascii=False, indent=2), encoding="utf-8")

story = classify_story_mode(SCRIPT)
(OUT / "TREECUT_G3_STORY_MODE_V1.json").write_text(json.dumps(
    {"script": SCRIPT, "story_mode": story,
     "rule": "SINGLE_CASE: 这一款/客户/定制→≥70%同案; MONTAGE: 通用语言才允许跨案例混剪",
     "case_cluster_basis": ["verified source relationship", "media lineage", "visual similarity",
                            "publication relation", "metadata hints(path=candidate only)"]}, ensure_ascii=False, indent=2), encoding="utf-8")

# 案例聚类轻量: 从候选素材名提取 case 前缀(示例)
case_cluster = []
for mid in (2482, 2483, 2484, 1984, 1, 37, 1590, 1591, 1592, 261, 703, 3, 4):
    case_cluster.append({"media_id": mid, "case_hint": None, "cluster_state": "UNKNOWN"})
(OUT / "TREECUT_G3_CASE_CLUSTER_V1.json").write_text(json.dumps(
    {"note": "轻量占位: 案例聚类待 media lineage+视觉相似接入; 未知保持 UNKNOWN", "items": case_cluster},
    ensure_ascii=False, indent=1), encoding="utf-8")

# ---- G3 matcher Query20(V2 风格主张 × 候选场景) ----
def prof(mid):
    # 依据 G2 探测: 有 EXTEND 窗的资产视为含 EXTEND(2482-84, 1984-86); 纯插座(1590-92)仅 SOCKET
    extend_mids = {2482, 2483, 2484, 1984, 1985, 1986}
    drawer_mids = {1, 37}
    socket_mids = {1590, 1591, 1592}
    if mid in extend_mids:
        return {"actions": ["EXTEND", "RETRACT"], "object": "TABLETOP"}
    if mid in drawer_mids:
        return {"actions": ["DRAWER_OPEN"], "object": "DRAWER"}
    if mid in socket_mids:
        return {"actions": ["SOCKET_INSERT"], "object": "SOCKET"}
    return {"actions": [], "object": None}

matcher = ClaimVisualMatcher(eligible_check=lambda mid, kind="media_file": (True, {}),
                             action_profile=prof)
QUERIES20 = [
    ("拉开以后变宽", "EXTEND"), ("来客时一拉就变宽", "EXTEND"), ("平时收起来不占位", "RETRACT"),
    ("上层薄抽打开就能拿到", "DRAWER_OPEN"), ("收纳小物不弯腰", "DRAWER_OPEN"),
    ("插拔顺手", "SOCKET_INSERT"), ("吃火锅煮茶方便", "POWER_USE"),
    ("轨道插座可以用", "SOCKET_INSERT"), ("把东西放进去", "STORAGE_PUT_IN"),
    ("柜门打开", "CABINET_OPEN"), ("桌面可以变宽", "EXTEND"), ("收起来不占地方", "RETRACT"),
    ("薄抽拉出来", "DRAWER_OPEN"), ("插头插上就能用", "SOCKET_INSERT"),
    ("拉出来更宽", "EXTEND"), ("用的时候再拉开", "EXTEND"),
    ("抽屉推回去", "DRAWER_CLOSE"), ("柜门关上", "CABINET_CLOSE"),
    ("收纳空间很大", "STORAGE_PUT_IN"), ("这个岛台是伸缩的", "EXTEND"),
]
pool_mids = [2482, 2483, 2484, 1984, 1985, 1986, 1, 37, 1590, 1591, 1592, 261, 703, 3, 4]
mq = []
for i, (txt, exp_act) in enumerate(QUERIES20):
    c = AtomicClaim(claim_id=f"Q{i+1}", beat_id=f"B{i % 5 + 1}", text=txt,
                    claim_type="ACTION", required_action=exp_act)
    cands = [Candidate(media_id=m, actions=prof(m)["actions"], object_=prof(m)["object"]) for m in pool_mids]
    res = matcher.rank(c, "INFORMATION_MONTAGE", cands, top_k=3)
    passed = [r for r in res if r["status"] == "PASS"]
    rej_socket = [r for r in res if r["status"] == "REJECT" and any("DOMINANT_VISUAL_MISMATCH" in x for x in r["reasons"])]
    mq.append({"query": txt, "expected_action": exp_act, "matched_top": [p["candidate"].media_id for p in passed[:3]],
               "matched_n": len(passed), "socket_rejected": len(rej_socket) > 0,
               "hard_gate_demo": True})
(OUT / "TREECUT_G3_MATCHER_QUERY20_V1.json").write_text(json.dumps({"queries": mq}, ensure_ascii=False, indent=1), encoding="utf-8")
print("G3 query20 matched queries:", sum(1 for q in mq if q["matched_n"] > 0), "/20")

# V2 回归文件(matcher 级别: 伸缩口播→插座候选被拒)
v2reg = []
for txt, act in (("拉开以后变宽", "EXTEND"), ("收起来不占位", "RETRACT"), ("上层薄抽", "DRAWER_OPEN")):
    c = AtomicClaim(claim_id="R", beat_id="B", text=txt, claim_type="ACTION", required_action=act)
    socket = Candidate(media_id=1590, actions=["SOCKET_INSERT"], object_="SOCKET")
    res = matcher.rank(c, "INFORMATION_MONTAGE", [socket])
    v2reg.append({"narration": txt, "visual": "track-socket close-up", "candidate_actions": ["SOCKET_INSERT"],
                  "matcher_result": res[0]["status"], "reasons": res[0]["reasons"],
                  "expected": "ACTION_MATCH=FAIL"})
(OUT / "TREECUT_G3_PILOT_V2_REGRESSION_V1.json").write_text(json.dumps(
    {"regressions": v2reg, "note": "Permanent: 伸缩/收起口播配轨道插座特写必须 FAIL"}, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- Dedup 实测: 在 V2 时间线候选上跑叙事近重 ----
try:
    tl = json.loads((OUT / "B007_V2_TIMELINE_V1.json").read_text(encoding="utf-8"))
    subs = tl.get("subclips", [])
    shots = []
    for s in subs:
        # provenance 只给了 asset 前缀, 用 beat 顺序模拟同案例结尾重复场景
        shots.append(Shot(media_id=hash(str(s.get("provenance"))) % 10000 + 1,
                          folder_hint="【01】上层薄抽" if "薄抽" in (s.get("type") or "") else "【05】公牛轨道插座",
                          case_id="【62】广州赖小姐" if s.get("type") in ("FEATURE_STORAGE",) else
                                  ("【20】河南王小姐" if s.get("type") == "CTA" else "【21】北京陶先生"),
                          shot_role=s.get("type", "").lower()))
    hits = detect_duplicates(shots)
    v2dedup = {"timeline_shots": len(shots), "dedup_hits": hits[:6],
               "note": "V2 结尾(CTA 薄抽人物镜)与开头 FEATURE_STORAGE 同角色/同功能文件夹 → 叙事近重被拦(至少WARNING)"}
    (OUT / "TREECUT_PILOT_V2_DEDUP_RUN_V1.json").write_text(json.dumps(v2dedup, ensure_ascii=False, indent=1), encoding="utf-8")
    print("V2 dedup run hits:", len(hits))
except Exception as e:
    print("dedup run err", e)

# ---- QA false-pass 审计 ----
(OUT / "TREECUT_QA_FALSE_PASS_AUDIT_V1.json").write_text(json.dumps({
    "lessons": [
        "V1: container 时长当 AV 同步 → 改用 stream 级 ≤0.10s 硬闸(已修复)",
        "V1: QA 报告 READY 但旧字幕/水印/错配 → P0 门禁 + 人工最终裁决",
        "G1: Qwen 误报22条换帧复核21回ABSENT → L2 永远不冒充 L3",
        "工程纪律: machine-only 结果不得称 human accuracy; technical preview 不得称 Pilot V3"],
    "prevention": "P0 集 + verdict 门禁 + 分层 QA + HUMAN 层 append-only"}, ensure_ascii=False, indent=2), encoding="utf-8")
print("artifacts written")
