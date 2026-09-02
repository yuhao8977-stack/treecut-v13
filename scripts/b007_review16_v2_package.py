# -*- coding: utf-8 -*-
"""V0.9 前准备：Review16 V2 完整审核包（关键帧+证据+AI候选） + 可填答案表。

16 段 = Historical 8（4op+4hi，来自 V0.8.1 calibration40/enrichment 的 b007 段）
      + Recent 8（4op+4hi，来自 RECENT12 calibration20 + qwen candidates）。
审核字段：scene/product/material/function/action/shot_function/business_feature/evidence_state。
"""
from __future__ import annotations

import base64
import csv
import json
import sqlite3
import sys
import time
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
R16 = OUT / "B007_L3_REVIEW16_V2.json"
REC_QW = OUT / "B007_RECENT12_QWENVL_CANDIDATES_V1.json"
HIST_QW = OUT / "B007_V081_QWENVL_VISUAL_CANDIDATES_V1.json"
CAL40 = OUT / "B007_V081_CALIBRATION40_V1.json"
REC_CAL = OUT / "B007_RECENT12_CALIBRATION20_V1.json"


def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()


def thumb_b64(path: str, max_side: int = 420) -> str | None:
    try:
        import cv2
        import numpy as np
        data = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        if scale < 1.0:
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 72])
        return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii") if ok else None
    except Exception:
        return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    r16 = json.loads(R16.read_text(encoding="utf-8"))
    cal40 = {x["segment_id"]: x for x in json.loads(CAL40.read_text(encoding="utf-8"))["segments"]}
    rec_cal = {x["segment_id"]: x for x in json.loads(REC_CAL.read_text(encoding="utf-8"))["segments"]}
    hist_qw = {s["segment_id"]: s for s in json.loads(HIST_QW.read_text(encoding="utf-8")).get("segments", [])}
    rec_qw = {s["segment_id"]: s for s in json.loads(REC_QW.read_text(encoding="utf-8")).get("segments", [])}

    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    kf = {}
    for r in q(c, "SELECT note_id, seg_no, image_path FROM b007_keyframe_v1"):
        kf.setdefault(r[0], {})[r[1]] = r[2]
    asr_all, ocr_all, vis_all = {}, {}, {}
    for r in q(c, "SELECT note_id, start_ms, end_ms, text FROM b007_asr_v1"):
        asr_all.setdefault(r[0], []).append(r[1:])
    for r in q(c, "SELECT note_id, frame_timestamp_ms, text FROM b007_ocr_v1"):
        ocr_all.setdefault(r[0], []).append(r[1:])
    for r in q(c, "SELECT note_id, frame_timestamp_ms, scene_family, confidence FROM b007_visual_evidence_v1"):
        vis_all.setdefault(r[0], []).append(r[1:])
    c.close()

    cards = []
    answers = []
    for part in ("historical", "recent"):
        for item in r16[part]:
            nid = item["note_id"]
            sid = item["segment_id"]
            cal = cal40.get(sid) or rec_cal.get(sid)
            start_ms = (cal or {}).get("start_ms", 0)
            end_ms = (cal or {}).get("end_ms", 0)
            seg_no = int(sid.rsplit(":", 1)[-1])
            qw = hist_qw.get(sid) or rec_qw.get(sid) or {}
            kf_path = kf.get(nid, {}).get(seg_no)
            b64 = thumb_b64(kf_path) if kf_path else None
            asr_txt = " ".join(r[2] for r in asr_all.get(nid, []) if r[0] < end_ms and r[1] > start_ms)[:400]
            ocr_txt = " ".join(r[1] for r in ocr_all.get(nid, []) if start_ms <= r[0] < end_ms)[:400]
            clip = [(r[1], r[2]) for r in vis_all.get(nid, []) if start_ms <= r[0] < end_ms]
            fields = qw.get("fields", {})
            def fv(k):
                v = fields.get(k, {})
                return f"{v.get('value','UNKNOWN')} [{v.get('source','UNKNOWN')}]" if isinstance(v, dict) else "UNKNOWN"
            qfields = "".join(
                f"<tr><td>{k}</td><td>{fv(k)}</td></tr>" for k in
                ("scene", "product", "material", "function", "action", "shot_function_candidate",
                 "human_presence", "product_visibility", "feature_demonstration", "detail_shot",
                 "storage_evidence", "power_evidence", "flexible_capacity_evidence", "dining_context_evidence"))
            cards.append(f"""
            <div class="card">
              <h3>{part.upper()} | {item['sample_id']} | {item['selection_role']} | {sid}
                  <span class="stratum">{item['stratum']}</span></h3>
              <p>time: {start_ms}–{end_ms} ms | keyframe: {kf_path or '-'}</p>
              <div class="row">
                <div>{'<img src="' + b64 + '"/>' if b64 else '<span class="noimg">no keyframe</span>'}</div>
                <div>
                  <b>ASR:</b> {asr_txt or '(无)'}<br/>
                  <b>OCR:</b> {ocr_txt or '(无)'}<br/>
                  <b>CLIP:</b> {json.dumps(clip, ensure_ascii=False)}<br/>
                  <table><tr><th>Qwen field (value [source])</th></tr>{qfields}</table>
                </div>
              </div>
              <p class="reviewhint">L3 审核（人工填写，SUPPORTED=明确看到 / CANDIDATE=像但不确定 / UNKNOWN=看不出）：
              scene / product / material / function / action / shot_function / business_feature</p>
            </div>""")
            answers.append({
                "part": part, "sample_id": item["sample_id"], "stratum": item["stratum"],
                "selection_role": item["selection_role"], "segment_id": sid,
                "start_ms": start_ms, "end_ms": end_ms,
                "human": {"scene": "", "product": "", "material": "", "function": "", "action": "",
                          "shot_function": "", "business_feature": "", "evidence_state": ""},
            })

    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>B007 L3 Review16 V2 — 完整审核包</title>
<style>
body{{font-family:sans-serif;margin:16px;background:#f7f7f7}}
.card{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px;margin:12px 0}}
.row{{display:flex;gap:16px}} .row>div:first-child img{{max-width:400px;border:1px solid #ccc}}
table{{border-collapse:collapse;margin-top:6px;font-size:12px}} td,th{{border:1px solid #ccc;padding:2px 6px}}
.stratum{{color:#666;font-weight:normal}} .noimg{{color:#999}}
.reviewhint{{color:#888;font-size:12px;border-top:1px dashed #ccc;margin-top:8px;padding-top:6px}}
</style></head><body>
<h1>B007 L3 Review16 V2 — 完整审核包（历史8 + 近期8）</h1>
<p>Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} | 每段：确认 AI 对错，只填人眼能确认的字段，其余留空 → 用答案表 CSV 交回</p>
{''.join(cards)}
</body></html>"""
    (OUT / "B007_L3_REVIEW16_V2.html").write_text(html, encoding="utf-8")

    with open(OUT / "B007_L3_REVIEW16_V2_ANSWERSHEET.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["part", "sample_id", "stratum", "role", "segment_id", "start_ms", "end_ms",
                    "scene", "product", "material", "function", "action", "shot_function",
                    "business_feature", "evidence_state"])
        for a in answers:
            w.writerow([a["part"], a["sample_id"], a["stratum"], a["selection_role"], a["segment_id"],
                        a["start_ms"], a["end_ms"], a["human"]["scene"], a["human"]["product"],
                        a["human"]["material"], a["human"]["function"], a["human"]["action"],
                        a["human"]["shot_function"], a["human"]["business_feature"],
                        a["human"]["evidence_state"]])
    print(json.dumps({"segments": len(answers), "html": str(OUT / "B007_L3_REVIEW16_V2.html"),
                      "answersheet": str(OUT / "B007_L3_REVIEW16_V2_ANSWERSHEET.csv")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
