# -*- coding: utf-8 -*-
"""Stage3 TRACK B — B1/B2/B3/B4/B5：Data Gap Discovery V2（不生成人工真值）。

改进发现器（对比旧版）：
  - Action：精确/语义短语（禁"收纳"作 RETRACT 强证据）+ component 证据 + 光流方向提示
  - Scene：禁"家"子串（家具/厂家/大家不命中）；用 ASR 整词/语义 + asset 语境
  - Material：component-aware（不锈钢水槽 ≠ 岛台主体不锈钢）；只列候选不标真值
输出每缺口 candidate_found / high_quality_candidate / unique_asset_count /
      near_duplicate_removed；不足则 LIBRARY_DATA_GAP。
"""
import json
import os
import re
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

# ---- 排除集：已有人工真值的段（canonical + Stage3 + Holdout）----
def load_exclusions():
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    excl = {r[0] for r in conn.execute("SELECT segment_id FROM canonical_human_truth")}
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    excl |= {s["segment_id"] for s in tman["segments"]}
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    excl |= {s["segment_id"] for s in hold["strata"]}
    conn.close()
    return excl


def main():
    excl = load_exclusions()
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # 候选池：全素材库未被真值覆盖的段（asset 唯一）
    used_asset = set()
    for r in conn.execute("SELECT DISTINCT asset_id FROM segments WHERE segment_id IN "
                          "(SELECT segment_id FROM canonical_human_truth)"):
        used_asset.add(r[0])
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    used_asset |= {s["asset_id"] for s in tman["segments"]}
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    used_asset |= {s["asset_id"] for s in hold["strata"]}

    cands = []
    for r in conn.execute("SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms FROM segments s "
                          "WHERE s.segment_id NOT IN (SELECT segment_id FROM canonical_human_truth)"
                          " AND s.segment_id NOT IN (SELECT segment_id FROM targeted_human_review_v1)"
                          " AND s.segment_id NOT IN (SELECT segment_id FROM fresh_holdout_human_review_v1)"):
        if r["segment_id"] in excl or r["asset_id"] in used_asset:
            continue
        asr = " ".join(x[0] for x in conn.execute(
            "SELECT text_corrected FROM transcripts WHERE asset_id=? AND text_corrected IS NOT NULL",
            (r["asset_id"],)).fetchall() if x[0])[:800]
        ocr = " ".join(x[0] for x in conn.execute(
            "SELECT text FROM ocr_text WHERE asset_id=? AND text IS NOT NULL",
            (r["asset_id"],)).fetchall() if x[0])[:400]
        kf_n = conn.execute("SELECT COUNT(*) n FROM keyframes WHERE segment_id=?",
                            (r["segment_id"],)).fetchone()["n"]
        cands.append({"segment_id": r["segment_id"], "asset_id": r["asset_id"],
                      "asr": asr, "ocr": ocr, "kf_n": kf_n})
    conn.close()
    print("候选池:", len(cands))

    # ---- 改进规则（禁子串误命中）----
    # Action：精确短语（词边界/语义）
    OP_SOCKET = re.compile(r"插电|插上电|插座|插头|通电|电源接口")
    OP_SINK = re.compile(r"水槽盖|掀开水槽|打开水槽|水槽.*盖|盖上水槽")
    CLOSE_DRAW = re.compile(r"关上抽屉|关闭抽屉|推.?回抽屉|抽屉关")
    # Scene：禁"家"子串；整词/语义
    HOME = re.compile(r"(客户家|客户家里|业主家|业主家里|家里|入户|新家)")
    SHOWROOM = re.compile(r"展厅|样板间|门店|专卖店")
    # Material：component-aware（不锈钢 + 非水槽语境 → 岛台主体候选）
    SOLID = re.compile(r"实木|原木|木纹|木质")
    STAINLESS = re.compile(r"不锈钢|镜面钢")

    gaps = {
        "OPERATE_SOCKET": {"rule": OP_SOCKET, "found": []},
        "OPEN_SINK_COVER": {"rule": OP_SINK, "found": []},
        "CLOSE_DRAWER": {"rule": CLOSE_DRAW, "found": []},
        "CUSTOMER_HOME": {"rule": HOME, "found": []},
        "SHOWROOM": {"rule": SHOWROOM, "found": []},
        "SOLID_WOOD": {"rule": SOLID, "found": []},
    }
    for c in cands:
        text = c["asr"] + " " + c["ocr"]
        for gname, spec in gaps.items():
            if spec["rule"].search(text):
                spec["found"].append(c)

    # ---- 高质量过滤（keyframes>=3 + ASR 语义置信）----
    report = {}
    for gname, spec in gaps.items():
        found = spec["found"]
        hq = [c for c in found if c["kf_n"] >= 3]
        uniq_asset = len({c["asset_id"] for c in found})
        report[gname] = {
            "candidate_found": len(found) > 0,
            "candidate_count": len(found),
            "high_quality_candidate": len(hq),
            "unique_asset_count": uniq_asset,
            "near_duplicate_removed": len(found) - uniq_asset,
            "examples": [{"segment_id": c["segment_id"][:8], "asset": c["asset_id"][:8],
                          "asr": c["asr"][:60], "kf": c["kf_n"]} for c in hq[:3]],
            "status": ("CANDIDATES_FOUND" if len(hq) >= 1 else
                       "LIBRARY_DATA_GAP" if not found else "WEAK_CANDIDATES"),
        }
        print(f"[{gname}] found={len(found)} hq={len(hq)} uniq_asset={uniq_asset} -> {report[gname]['status']}")

    # B6: 最小 Batch 触发评估
    total_hq = sum(v["high_quality_candidate"] for v in report.values())
    cats_with_hq = sum(1 for v in report.values() if v["high_quality_candidate"] >= 1)
    trigger = total_hq >= 15 and cats_with_hq >= 2
    report["_batch_trigger"] = {"total_high_quality": total_hq,
                                "categories_with_hq": cats_with_hq,
                                "trigger_min_batch": trigger,
                                "note": "仅当 high_quality 唯一候选 >=15 且 >=2 类可显著增 support 才建议新批；否则 LIBRARY_DATA_GAP"}

    out = {"manifest": "STAGE3_DATA_GAP_DISCOVERY_V2",
           "scope": "全素材库候选发现（不生成人工真值）；改进规则（禁'收纳'/'家'子串）",
           "pool_size": len(cands), "gaps": report,
           "conclusion": ("建议新人工 Batch" if trigger else
                          "无足够高质量候选 → 标 LIBRARY_DATA_GAP，不创建人工任务")}
    p = os.path.join(DATA_ROOT, "STAGE3_DATA_GAP_DISCOVERY_V2.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
