# -*- coding: utf-8 -*-
"""Stage3 POST-REVIEW — STEP 8/9/10：Variant / Scene / Material 真实增量（60 vs Cal333）。"""
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    man = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    man_sids = [s["segment_id"] for s in man["segments"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ph = ",".join("?" * len(man_sids))
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", man_sids)]
    cal = [dict(r) for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1")]
    conn.close()

    def scnt(rs, f):
        return dict(Counter(r.get(f) for r in rs if r.get(f)))

    def mcnt(rs, f):
        c = Counter()
        for r in rs:
            for x in jload(r.get(f)):
                c[x] += 1
        return dict(c)

    out = {}
    print("=== STEP 8: Product Variant ===")
    for f in ("product_variant", "product_family"):
        e = scnt(cal, f); n = scnt(rows, f)
        comb = Counter(e); [comb.__setitem__(k, comb.get(k, 0) + v) for k, v in n.items()]
        out[f] = {"existing_333": e, "new_60": n, "combined": dict(comb)}
        print(f"[{f}] 333={e}")
        print(f"[{f}] 60={n}")
    for v in ("FLOATING_ISLAND", "FLOOR_ISLAND"):
        tot = out["product_variant"]["combined"].get(v, 0)
        out.setdefault("variant_gap", {})[v] = "INSUFFICIENT_SAMPLE/LIBRARY_GAP" if tot == 0 else f"present({tot})"
        print(f"  变体 {v}: combined={tot}")

    print("\n=== STEP 9: Scene ===")
    for f in ("scene_family", "scene_subtype"):
        e = scnt(cal, f); n = scnt(rows, f)
        comb = Counter(e); [comb.__setitem__(k, comb.get(k, 0) + v) for k, v in n.items()]
        out[f] = {"existing_333": e, "new_60": n, "combined": dict(comb)}
        print(f"[{f}] 333={e}")
        print(f"[{f}] 60={n}")
    # Scene 候选命中：V3_1 中 selection_reason=scene 的段（4 条）真值
    scene_cand = [s for s in man["segments"] if s["sampling_target"] == "SCENE"]
    man_by = {r["segment_id"]: r for r in rows}
    scene_hits = []
    for s in scene_cand:
        t = man_by.get(s["segment_id"], {})
        scene_hits.append({"segment_id": s["segment_id"], "kw": s.get("sampling_keywords", []),
                           "truth_scene_family": t.get("scene_family"),
                           "truth_scene_subtype": t.get("scene_subtype")})
    real_scene = sum(1 for h in scene_hits if h["truth_scene_family"] in
                     ("CUSTOMER_HOME", "SHOWROOM", "INSTALLATION_SITE"))
    out["scene_candidate_discovery"] = {"candidates": len(scene_hits), "real_longtail": real_scene,
                                        "discovery_precision": round(real_scene / len(scene_hits) * 100, 1)
                                        if scene_hits else 0, "detail": scene_hits}
    print(f"Scene 候选 {len(scene_hits)} 条，真 longtail {real_scene} 条")

    print("\n=== STEP 10: Material ===")
    e = mcnt(cal, "material_multi"); n = mcnt(rows, "material_multi")
    comb = Counter(e); [comb.__setitem__(k, comb.get(k, 0) + v) for k, v in n.items()]
    out["material"] = {"existing_333": e, "new_60": n, "combined": dict(comb)}
    print(f"[material] 333={e}")
    print(f"[material] 60={n}")
    mat_cand = [s for s in man["segments"] if s["sampling_target"] == "MATERIAL"]
    mat_hits = []
    for s in mat_cand:
        t = man_by.get(s["segment_id"], {})
        mat_hits.append({"segment_id": s["segment_id"], "kw": s.get("sampling_keywords", []),
                         "truth_material": jload(t.get("material_multi"))})
    real_mat = sum(1 for h in mat_hits if h["truth_material"] and h["truth_material"] != ["UNKNOWN"])
    out["material_candidate_discovery"] = {"candidates": len(mat_hits), "real_material": real_mat,
                                           "detail": mat_hits}
    print(f"Material 候选 {len(mat_hits)} 条，真标注材质 {real_mat} 条")
    for m in ("实木", "奢石", "大理石", "不锈钢", "玻璃"):
        tot = out["material"]["combined"].get(m, 0)
        out.setdefault("material_gap", {})[m] = ("INSUFFICIENT_SAMPLE" if tot < 5 else f"OK({tot})")
        print(f"  材质 {m}: combined={tot}")

    p = os.path.join(DATA_ROOT, "STAGE3_POST_REVIEW_LABEL_SUPPORT.json")
    support = json.load(open(p, encoding="utf-8"))
    support["step8_10_detail"] = out
    json.dump(support, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n-> 已并入 STAGE3_POST_REVIEW_LABEL_SUPPORT.json")


if __name__ == "__main__":
    main()
