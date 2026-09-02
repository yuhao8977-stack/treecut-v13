# -*- coding: utf-8 -*-
"""V0.8.1 — Qwen2.5-VL 7B 第二视觉认知器（VISUAL_COGNITION_CANDIDATE_V2）。

严格 14 字段 schema；UNKNOWN 合法；来源分离（VISUAL/ASR/OCR/MULTIMODAL/MODEL_INFERENCE_ONLY）；
仅 L2 CANDIDATE；不喂 performance 数据；不写 L3。
用法: python b007_v081_qwen.py [--segments N] [--dry]
"""
from __future__ import annotations

import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

DATA_ROOT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = DATA_ROOT / "database" / "materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
CAL = OUT / "B007_V081_CALIBRATION40_V1.json"
API = "http://localhost:11434/api/generate"

FIELDS = ["scene", "product", "material", "function", "action",
          "shot_function_candidate", "human_presence", "product_visibility",
          "feature_demonstration", "detail_shot", "storage_evidence",
          "power_evidence", "flexible_capacity_evidence", "dining_context_evidence"]
SOURCES = ["VISUAL_EVIDENCE", "ASR_EVIDENCE", "OCR_EVIDENCE", "MULTIMODAL_SUPPORT",
           "MODEL_INFERENCE_ONLY", "UNKNOWN"]

PROMPT_TMPL = """你是 TreeCut 的视频画面认知器。规则：
1) 视觉字段(scene/product/material/function/action/shot_function_candidate/human_presence/product_visibility/feature_demonstration/detail_shot)只依据【画面关键帧】回答，来源=VISUAL_EVIDENCE。
2) 业务证据字段(storage_evidence/power_evidence/flexible_capacity_evidence/dining_context_evidence)：若画面直接可见→VISUAL_EVIDENCE；若画面+文字共同支持→MULTIMODAL_SUPPORT；若仅 ASR/OCR 提及→分别标 ASR_EVIDENCE/OCR_EVIDENCE（禁止伪装成视觉证据）；若画面无法判断→UNKNOWN。
3) 无法从画面确定一律 UNKNOWN，禁止猜测提高覆盖率。
4) scene 枚举：FACTORY/CUSTOMER_HOME/SHOWROOM/INSTALLATION_SITE/OTHER/UNKNOWN。
5) product/material/function/action/shot_function_candidate 用简短术语或 UNKNOWN。
6) 其余字段值用 yes/no/UNKNOWN。
输出严格 JSON：{{"scene":{{"value":"..","source":".."}}, ...14字段...}}

画面上下文（仅供 ASR/OCR 来源标注，不得当作视觉证据）：
ASR: {asr}
OCR: {ocr}"""


def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()


def load_image_b64(path: Path, max_side: int = 1024) -> str | None:
    try:
        import cv2
        import numpy as np
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        if scale < 1.0:
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return None
        return base64.b64encode(buf.tobytes()).decode("ascii")
    except Exception:
        return None


def call_qwen(prompt: str, img_b64: str | None, timeout: int = 300) -> dict | None:
    payload = {"model": "qwen2.5vl:7b", "prompt": prompt, "stream": False,
               "options": {"temperature": 0.0, "num_predict": 800}}
    if img_b64:
        payload["images"] = [img_b64]
    req = urllib.request.Request(API, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data


def parse_response(text: str) -> dict:
    text = (text or "").strip()
    # 提取 JSON 对象
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        obj = json.loads(text)
    except Exception:
        obj = {}
    out = {}
    for f in FIELDS:
        v = obj.get(f, {})
        if isinstance(v, dict):
            out[f] = {"value": str(v.get("value", "UNKNOWN")), "source": str(v.get("source", "UNKNOWN"))}
        else:
            out[f] = {"value": str(v) if v else "UNKNOWN", "source": "UNKNOWN"}
        if out[f]["source"] not in SOURCES:
            out[f]["source"] = "UNKNOWN"
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cal", default=str(CAL))
    ap.add_argument("--out", default="B007_V081_QWENVL_VISUAL_CANDIDATES_V1.json")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    cal = json.loads(Path(args.cal).read_text(encoding="utf-8"))
    segs = cal["segments"]
    import sqlite3
    c = sqlite3.connect("file:" + str(DB).replace("\\", "/") + "?mode=ro", uri=True)
    kf = {}
    for r in q(c, "SELECT note_id, seg_no, image_path, timestamp_ms FROM b007_keyframe_v1"):
        kf.setdefault(r[0], {})[r[1]] = {"path": r[2], "ts": r[3]}
    asr_all = {}
    for r in q(c, "SELECT note_id, start_ms, end_ms, text FROM b007_asr_v1"):
        asr_all.setdefault(r[0], []).append(r)
    ocr_all = {}
    for r in q(c, "SELECT note_id, frame_timestamp_ms, text FROM b007_ocr_v1"):
        ocr_all.setdefault(r[0], []).append(r)
    clip_all = {}
    for r in q(c, "SELECT note_id, frame_timestamp_ms, scene_family, confidence FROM b007_visual_evidence_v1"):
        clip_all.setdefault(r[0], []).append(r)
    c.close()

    results = []
    for i, s in enumerate(segs):
        nid, seg_no = s["note_id"], s["seg_no"]
        k = kf.get(nid, {}).get(seg_no)
        img_b64 = load_image_b64(Path(k["path"])) if k and k.get("path") else None
        asr_txt = " ".join(r[3] for r in asr_all.get(nid, [])
                           if r[1] < s["end_ms"] and r[2] > s["start_ms"])[:600]
        ocr_txt = " ".join(r[2] for r in ocr_all.get(nid, [])
                           if s["start_ms"] <= r[1] < s["end_ms"])[:600]
        clip = [(r[2], r[3]) for r in clip_all.get(nid, [])
                if s["start_ms"] <= r[1] < s["end_ms"]]
        prompt = PROMPT_TMPL.format(asr=asr_txt or "(无)", ocr=ocr_txt or "(无)")
        rec = {"segment_id": s["segment_id"], "sample_id": s["sample_id"], "note_id": nid,
               "seg_no": seg_no, "start_ms": s["start_ms"], "end_ms": s["end_ms"],
               "selection_role": s["selection_role"], "status": "CANDIDATE",
               "model": "qwen2.5vl:7b", "source_name": "VISUAL_COGNITION_CANDIDATE_V2"}
        try:
            resp = call_qwen(prompt, img_b64)
            parsed = parse_response(resp.get("response", ""))
            rec["fields"] = parsed
            rec["qwen_raw_tail"] = (resp.get("response") or "")[-120:]
            rec["ok"] = True
        except Exception as e:
            rec["ok"] = False
            rec["error"] = str(e)[:200]
            rec["fields"] = {f: {"value": "UNKNOWN", "source": "UNKNOWN"} for f in FIELDS}
        rec["context"] = {"keyframe": k["path"] if k else None,
                          "asr_text": asr_txt, "ocr_text": ocr_txt,
                          "clip_frames": clip}
        results.append(rec)
        print(f"[{i + 1}/40] {s['segment_id']} ok={rec['ok']}")
        # 每 5 条保存一次（防崩溃丢进度）
        if (i + 1) % 5 == 0:
            (OUT / args.out).write_text(
                json.dumps({"phase": "V0.8.1", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "model": "qwen2.5vl:7b", "status_policy": "L2 CANDIDATE only; no auto L3",
                            "segments": results}, ensure_ascii=False, indent=1), encoding="utf-8")

    ok_n = sum(1 for r in results if r.get("ok"))
    (OUT / args.out).write_text(
        json.dumps({"phase": "V0.8.1", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "model": "qwen2.5vl:7b", "status_policy": "L2 CANDIDATE only; no auto L3",
                    "count": len(results), "ok": ok_n,
                    "segments": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"segments": len(results), "ok": ok_n}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
