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

    CN_FIELD = {"scene": "场景", "product": "产品", "material": "材质", "function": "功能",
                "action": "动作", "shot_function_candidate": "镜头用途(候选)",
                "human_presence": "人物出现", "product_visibility": "产品可见",
                "feature_demonstration": "功能演示", "detail_shot": "细节特写",
                "storage_evidence": "收纳证据", "power_evidence": "电源/插座证据",
                "flexible_capacity_evidence": "伸缩容量证据",
                "dining_context_evidence": "餐边/餐桌语境"}
    CN_SRC = {"VISUAL_EVIDENCE": "画面证据", "ASR_EVIDENCE": "口播证据", "OCR_EVIDENCE": "画面文字证据",
              "MULTIMODAL_SUPPORT": "多模态支持", "MODEL_INFERENCE_ONLY": "模型推断",
              "UNKNOWN": "未知"}
    CN_SCENE = {"FACTORY": "工厂", "CUSTOMER_HOME": "客户家", "SHOWROOM": "展厅",
                "INSTALLATION_SITE": "安装现场", "OTHER": "其他", "UNKNOWN": "未知"}
    CN_ROLE = {"OPENING_SEGMENT": "开头段", "HIGH_INFORMATION_SEGMENT": "高信息段",
               "OPENING": "开头", "HIGH": "高信息"}
    CN_PART = {"historical": "历史样本", "recent": "近期样本"}

    def cn_val(field, val):
        if field == "scene":
            return CN_SCENE.get(val, val)
        if val in ("yes", "no"):
            return {"yes": "是", "no": "否"}[val]
        return val

    def cn_field_line(field, v):
        if not isinstance(v, dict):
            return f"{CN_FIELD.get(field, field)}: UNKNOWN"
        val = cn_val(field, v.get("value", "UNKNOWN"))
        src = CN_SRC.get(v.get("source", "UNKNOWN"), v.get("source", "UNKNOWN"))
        return f"{CN_FIELD.get(field, field)}：{val}（{src}）"

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
            clip = [(CN_SCENE.get(r[1], r[1]), r[2]) for r in vis_all.get(nid, []) if start_ms <= r[0] < end_ms]
            fields = qw.get("fields", {})
            qlines = "".join(f"<li>{cn_field_line(k, fields.get(k))}</li>"
                             for k in ("scene", "product", "material", "function", "action",
                                       "shot_function_candidate", "human_presence",
                                       "product_visibility", "feature_demonstration", "detail_shot",
                                       "storage_evidence", "power_evidence",
                                       "flexible_capacity_evidence", "dining_context_evidence"))
            sec_str = f"{start_ms / 1000:.1f} ~ {end_ms / 1000:.1f} 秒"
            cards.append(f"""
            <div class="card">
              <h3>{CN_PART[part]} | {item['sample_id']} | {CN_ROLE.get(item['selection_role'], item['selection_role'])}
                  <span class="stratum">{item['stratum']}</span></h3>
              <p>时间：{sec_str} | 关键帧：{kf_path or '无'}</p>
              <div class="row">
                <div>{'<img src="' + b64 + '"/>' if b64 else '<span class="noimg">无关键帧</span>'}</div>
                <div>
                  <p><b>画面口播(ASR)：</b>{asr_txt or '(无)'}</p>
                  <p><b>画面文字(OCR)：</b>{ocr_txt or '(无)'}</p>
                  <p><b>CLIP 场景判断：</b>{json.dumps(clip, ensure_ascii=False) or '(无)'}</p>
                  <p><b>Qwen 画面判断：</b></p>
                  <ul>{qlines}</ul>
                </div>
              </div>
              <p class="reviewhint">请人工核对（只填人眼能确认的）：<br/>
              场景对不对？产品是什么？有没有明显材质？在演示什么功能？人在做什么？属于全景/细节/功能演示/人物/其他？<br/>
              收纳/插座电源/伸缩/餐边 有没有明显看到？<br/>
              结论：SUPPORTED=画面明确看到 &nbsp; CANDIDATE=像但不确定 &nbsp; UNKNOWN=看不出</p>
            </div>""")
            answers.append({
                "part": CN_PART[part], "sample_id": item["sample_id"], "stratum": item["stratum"],
                "selection_role": CN_ROLE.get(item["selection_role"], item["selection_role"]),
                "segment_id": sid, "start_ms": start_ms, "end_ms": end_ms,
                "human": {"scene": "", "product": "", "material": "", "function": "", "action": "",
                          "shot_function": "", "business_feature": "", "evidence_state": ""},
            })

    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>B007 L3 Review16 V2 — 人工审核包</title>
<style>
body{{font-family:sans-serif;margin:16px;background:#f7f7f7}}
.card{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px;margin:12px 0}}
.row{{display:flex;gap:16px;flex-wrap:wrap}} .row>div:first-child img{{max-width:400px;border:1px solid #ccc}}
ul{{margin:2px 0 2px 18px;font-size:13px;line-height:1.7}}
.stratum{{color:#666;font-weight:normal}} .noimg{{color:#999}}
.reviewhint{{color:#a33;font-size:13px;border-top:1px dashed #ccc;margin-top:8px;padding-top:6px}}
</style></head><body>
<h1>B007 L3 Review16 V2 — 人工审核包（历史8 + 近期8）</h1>
<p>生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')} | 每段看左边画面，对照右边 AI 判断，把能确认的告诉我就行（可直接在聊天里说，也可填答案表）</p>
{''.join(cards)}
</body></html>"""
    (OUT / "B007_L3_REVIEW16_V2.html").write_text(html, encoding="utf-8")

    with open(OUT / "B007_L3_REVIEW16_V2_ANSWERSHEET.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["分组", "样本", "分层", "角色", "segment_id", "开始毫秒", "结束毫秒",
                    "场景", "产品", "材质", "功能", "动作", "镜头用途",
                    "业务特征(storage/power/flexible/dining)", "结论(SUPPORTED/CANDIDATE/UNKNOWN)"])
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
