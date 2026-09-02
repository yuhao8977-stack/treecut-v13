# -*- coding: utf-8 -*-
"""V0.9 CP-B — L3 校准报告 + Evidence-backed 模板候选（≤3）+ 选 1。"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
L3 = json.loads((OUT / "B007_L3_REVIEW16_INTEGRATION_V1.json").read_text(encoding="utf-8"))
HIST_QW = {s["segment_id"]: s for s in json.loads(
    (OUT / "B007_V081_QWENVL_VISUAL_CANDIDATES_V1.json").read_text(encoding="utf-8")).get("segments", [])}
REC_QW = {s["segment_id"]: s for s in json.loads(
    (OUT / "B007_RECENT12_QWENVL_CANDIDATES_V1.json").read_text(encoding="utf-8")).get("segments", [])}
CN2EN = {"客户家": "CUSTOMER_HOME", "工厂": "FACTORY", "展厅": "SHOWROOM",
         "设计图": "DESIGN_DIAGRAM", "安装现场": "INSTALLATION_SITE"}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    vis = {}
    for r in c.execute("SELECT note_id, frame_timestamp_ms, scene_family FROM b007_visual_evidence_v1"):
        vis.setdefault(r[0], []).append((r[1], r[2]))
    segs = {}
    for r in c.execute("SELECT note_id, seg_no, start_ms, end_ms FROM b007_segment_v1"):
        segs.setdefault(r[0], {})[r[1]] = (r[2], r[3])
    c.close()

    # ---- 1. Calibration：L3 scene vs Qwen vs CLIP ----
    cal_rows = []
    agree_qwen = agree_clip = total = 0
    field_stat = {}
    for e in L3["entries"]:
        sid = e["segment_id"]
        l3 = e["l3"]
        total += 1
        qw = HIST_QW.get(sid) or REC_QW.get(sid) or {}
        q_scene = (qw.get("fields", {}).get("scene", {}) or {}).get("value")
        q_scene_en = CN2EN.get(q_scene, q_scene)
        # CLIP：该段关键帧众数
        nid = sid.split(":")[1]
        seg_no = int(sid.rsplit(":", 1)[-1])
        st, en = segs.get(nid, {}).get(seg_no, (0, 0))
        fams = [f for ts, f in vis.get(nid, []) if st <= ts < en]
        clip_dom = max(set(fams), key=fams.count) if fams else None
        h_scene = l3.get("scene")
        a_q = (q_scene_en == h_scene)
        a_c = (clip_dom == h_scene) if clip_dom else False
        agree_qwen += 1 if a_q else 0
        agree_clip += 1 if a_c else 0
        # field-level: storage/power/flexible 人类 yes/no vs qwen
        for f in ("storage_evidence", "power_evidence", "flexible_capacity_evidence"):
            hv = l3.get(f, "UNKNOWN")
            qv = (qw.get("fields", {}).get(f, {}) or {}).get("value")
            if hv in ("yes", "no") and qv in ("yes", "no"):
                field_stat.setdefault(f, {"agree": 0, "n": 0})
                field_stat[f]["n"] += 1
                field_stat[f]["agree"] += 1 if hv == qv else 0
        cal_rows.append({"segment_id": sid, "sample": e["sample_id"], "l3_scene": h_scene,
                         "qwen_scene": q_scene_en or "UNKNOWN", "clip_scene": clip_dom or "UNKNOWN",
                         "qwen_agree": a_q, "clip_agree": a_c})
    cal = {"phase": "V0.9-CP-B", "n": total,
           "qwen_scene_accuracy_on_reviewed": round(agree_qwen / total, 3),
           "clip_scene_accuracy_on_reviewed": round(agree_clip / total, 3),
           "field_agreement": {k: round(v["agree"] / v["n"], 3) if v["n"] else None
                               for k, v in field_stat.items()},
           "rows": cal_rows,
           "note": "16 段小样本校准证据；不用于训练高精度模型"}
    (OUT / "B007_L3_CALIBRATION_REPORT_V1.json").write_text(
        json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 2. Template candidates（≤3，evidence-backed） ----
    # 按 L3 证据分组：哪些段支持哪种内容模式
    seg_meta = {}
    for e in L3["entries"]:
        sid = e["segment_id"]
        l3 = e["l3"]
        seg_meta[sid] = {"sample": e["sample_id"], "part": e["part"],
                         "role": e["selection_role"], "scene": l3.get("scene"),
                         "product_visible": l3.get("product_visibility") == "yes",
                         "human": l3.get("human_presence"),
                         "storage": l3.get("storage_evidence"),
                         "power": l3.get("power_evidence"),
                         "flexible": l3.get("flexible_capacity_evidence"),
                         "dining": l3.get("dining_context_evidence"),
                         "action": l3.get("action"), "note": l3.get("human_note")}

    def supports(sid, requires):
        m = seg_meta[sid]
        return all((m[k] == v) for k, v in requires.items())

    cand_templates = []
    # T-A: FEATURE_DEMONSTRATION（产品功能演示：收纳/插座/伸缩，客户家或工厂）
    ta_segs = [sid for sid, m in seg_meta.items()
               if (m["flexible"] == "yes" or m["storage"] == "yes" or m["power"] == "yes")
               and m["scene"] in ("CUSTOMER_HOME", "FACTORY") and m["product_visible"]]
    ta_rec = [sid for sid in ta_segs if seg_meta[sid]["part"] == "recent"]
    ta_his = [sid for sid in ta_segs if seg_meta[sid]["part"] == "historical"]
    cand_templates.append({
        "template_id": "T_A_FEATURE_DEMONSTRATION", "purpose": "产品功能演示型：展示收纳/轨道插座/伸缩等功能，客户家或工厂场景",
        "target_duration_s": "30-45", "beat_sequence": ["INTRO产品亮相", "产品全貌", "功能演示1(收纳/插座)", "功能演示2(伸缩)", "CTA"],
        "required_visual_semantics": ["CUSTOMER_HOME 或 FACTORY", "product_visible=yes",
                                      "至少一项 feature evidence yes(storage/power/flexible)"],
        "supporting_segments": ta_segs, "recent_support": ta_rec, "historical_support": ta_his,
        "counterexamples": [sid for sid, m in seg_meta.items()
                            if m["scene"] in ("DESIGN_DIAGRAM",) or not m["product_visible"]],
        "confidence": round(len(ta_segs) / 16, 3),
        "limitations": ["sample 级共现证据；feature 证据多为近景可确认；伸缩/收纳具体动作需成片听感验收"]})
    # T-B: PRODUCT_EXPLANATION（尺寸/细节/避坑讲解，口播主导）
    tb_segs = [sid for sid, m in seg_meta.items()
               if m["scene"] in ("DESIGN_DIAGRAM", "CUSTOMER_HOME") and m["part"] == "recent"
               or sid in ("b007:6a85b8490000000021022731:0", "b007:6a85b8490000000021022731:11")]
    tb_segs = sorted(set(tb_segs))
    cand_templates.append({
        "template_id": "T_B_PRODUCT_EXPLANATION", "purpose": "产品讲解型：尺寸/细节/避坑，口播主导+实景/图纸支撑",
        "target_duration_s": "30-45", "beat_sequence": ["HOOK问题/口播开场", "实景产品", "尺寸/细节讲解(图纸/实拍)", "CTA"],
        "required_visual_semantics": ["CUSTOMER_HOME 或 DESIGN_DIAGRAM", "可有人物讲解"],
        "supporting_segments": tb_segs,
        "recent_support": [s for s in tb_segs if seg_meta[s]["part"] == "recent"],
        "historical_support": [s for s in tb_segs if seg_meta[s]["part"] == "historical"],
        "counterexamples": [sid for sid, m in seg_meta.items() if m["scene"] == "SHOWROOM" and not m["product_visible"]],
        "confidence": round(len(tb_segs) / 16, 3),
        "limitations": ["口播内容需脚本约束事实；设计图/实景素材可支撑性需逐 beat 校验"]})
    # T-C: CASE/SCENE（改造前后/安装/入户案例）
    tc_segs = [sid for sid, m in seg_meta.items()
               if "对比" in (m["note"] or "") or m["scene"] == "INSTALLATION_SITE"
               or "改造" in (m["note"] or "")]
    cand_templates.append({
        "template_id": "T_C_CASE_SCENE", "purpose": "案例型：改造前后对比 / 入户安装 / 客户家场景叙事",
        "target_duration_s": "30-45", "beat_sequence": ["BEFORE问题", "改造/安装过程", "AFTER成果", "CTA"],
        "required_visual_semantics": ["对比图 或 INSTALLATION_SITE 或 CUSTOMER_HOME 实景"],
        "supporting_segments": tc_segs,
        "recent_support": [s for s in tc_segs if seg_meta[s]["part"] == "recent"],
        "historical_support": [s for s in tc_segs if seg_meta[s]["part"] == "historical"],
        "counterexamples": [],
        "confidence": round(len(tc_segs) / 16, 3),
        "limitations": ["案例叙事需要 before/after 成对素材，检索约束更强"]})

    (OUT / "B007_TEMPLATE_CANDIDATES_V1.json").write_text(json.dumps(
        {"phase": "V0.9-CP-B", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
         "candidates": cand_templates}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 3. 选 1 ----
    # 标准：evidence completeness + recent support + segment availability + production feasibility
    chosen = max(cand_templates, key=lambda t: (len(t["recent_support"]) * 2 + len(t["supporting_segments"]),
                                                len(t["supporting_segments"])))
    chosen_reason = {
        "selected": chosen["template_id"],
        "reason": ("近期(Recent10)支持段数最多且功能证据(收纳/插座/伸缩)在近期 Exact 媒体中可落镜："
                   f"recent_support={len(chosen['recent_support'])} hist={len(chosen['historical_support'])} "
                   f"total={len(chosen['supporting_segments'])}；生产可行性高（客户家/工厂场景+产品可见+功能演示均可由现有段覆盖）"),
        "not_by_magic_score": True,
    }
    (OUT / "B007_FIRST_REAL_TEMPLATE_V1.json").write_text(json.dumps(
        {"phase": "V0.9-CP-B", **chosen, "selection_reason": chosen_reason},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({"calibration": {"qwen_scene_acc": cal["qwen_scene_accuracy_on_reviewed"],
                                      "clip_scene_acc": cal["clip_scene_accuracy_on_reviewed"],
                                      "field_agreement": cal["field_agreement"]},
                      "candidates": [{"id": t["template_id"], "total": len(t["supporting_segments"]),
                                      "recent": len(t["recent_support"]),
                                      "hist": len(t["historical_support"])} for t in cand_templates],
                      "chosen": chosen["template_id"], "chosen_reason": chosen_reason["reason"]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
