#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MMVV A1 — Human Ground-Truth ROI 标注服务（最小本地工具，仅服务 A1；非 Workbench）。

运行: python tools/mmv_a1_annotate/server.py --port 8933   (仅 127.0.0.1)
功能: 逐案例/逐帧画框 + 标签(10 类) + 保存 → TREECUT_MMVV_HUMAN_GT_ROI_A1.json。
原则: 只存 L3_HUMAN_ROI；不生成/不读取 Qwen/heuristic ROI。
"""
import argparse, json, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]                       # repo root (tools/mmv_a1_annotate -> x2)
OUT = REPO / "reports" / "storage"
MANIFEST = OUT / "TREECUT_MMVV_A1_FRAME_MANIFEST.json"
ROI_FILE = OUT / "TREECUT_MMVV_HUMAN_GT_ROI_A1.json"
STATE_FILE = OUT / "TREECUT_MMVV_A1_ANNOTATION_STATE.json"
INDEX = Path(__file__).parent / "index.html"
AUX_HTML = Path(__file__).parent / "aux52.html"
A21_HTML = Path(__file__).parent / "a21_bind.html"
AUX_SELECT_FILE = OUT / "TREECUT_MMVV_A1_AUX52_SELECTION.json"
A21_BIND_FILE = OUT / "TREECUT_MMVV_A21_TARGET_BINDING.json"
A3_HTML = Path(__file__).parent / "a3_screen.html"
A3_CANDS_FILE = OUT / "TREECUT_MMVV_A3_CANDIDATES.json"
A3_SCREEN_FILE = OUT / "TREECUT_MMVV_A3_SCREENING.json"
A3_ROI_HTML = Path(__file__).parent / "a3_roi.html"
A3_HOLDOUT_FILE = OUT / "TREECUT_MMVV_A3_HOLDOUT_MANIFEST.json"
A3_ROI_FILE = OUT / "TREECUT_MMVV_A3_HUMAN_GT_ROI.json"
A3_BLIND_FILE = OUT / "TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json"
A3_ROI_BLIND_FILE = OUT / "TREECUT_MMVV_A3_HUMAN_GT_ROI_BLIND.json"
A3_OBS_HTML = OUT / "TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY_REVIEW.html"
A3_OBS_HUMAN_FILE = OUT / "TREECUT_MMVV_A3_OBSERVABILITY_HUMAN_V1.json"
A3_BLIND_FRAMES_DIR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_a3_blind_frames")
# Observability 人工判断允许枚举（内部英文，界面中文）
OBS_LABELS = {"ACTION_PROCESS_VISIBLE", "ENDPOINTS_ONLY", "MOSTLY_STATIC", "UNCLEAR"}


def _a3_thumbs_dir() -> Path:
    return Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_a3_frames") / "thumbs"


def _a3_holdout_frames_dir() -> Path:
    man = json.loads(A3_HOLDOUT_FILE.read_text(encoding="utf-8"))
    return Path(man.get("frames_dir"))


def load_a3_rois():
    if A3_ROI_FILE.exists():
        return json.loads(A3_ROI_FILE.read_text(encoding="utf-8"))
    return {"annotation_version": "A3", "annotation_source": "L3_HUMAN_ROI",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reviewer": None, "annotations": []}


def save_a3_rois(doc):
    doc["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = A3_ROI_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(A3_ROI_FILE)


def load_a3_blind_rois():
    if A3_ROI_BLIND_FILE.exists():
        return json.loads(A3_ROI_BLIND_FILE.read_text(encoding="utf-8"))
    return {"annotation_version": "A3_BLIND", "annotation_source": "L3_HUMAN_ROI",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reviewer": None, "annotations": []}


def save_a3_blind_rois(doc):
    doc["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = A3_ROI_BLIND_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(A3_ROI_BLIND_FILE)


def load_a3_obs_human():
    if A3_OBS_HUMAN_FILE.exists():
        return json.loads(A3_OBS_HUMAN_FILE.read_text(encoding="utf-8"))
    return {"experiment": "MMVV_A3_OBSERVABILITY_HUMAN_V1", "review_version": "V1",
            "reviewed_at": None, "answers": [], "done": 0}


def save_a3_obs_human(doc):
    tmp = A3_OBS_HUMAN_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(A3_OBS_HUMAN_FILE)


def _frames_dir() -> Path:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return Path(man.get("frames_dir"))


def _aux_dir() -> Path:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return Path(man.get("frames_dir")) / "aux52"

LABELS = ["TABLETOP", "EXTENSION_TABLETOP", "DRAWER", "UPPER_THIN_DRAWER", "TRACK_SOCKET",
          "SOCKET_MODULE", "PERSON", "HAND", "ISLAND_BODY", "OTHER_MOVING_PART"]
# A3 blind ROI 允许对象集（架构师 2026-09-05 扩展：+水槽/柜门/岩板桌腿/亚克力桌腿）
A3_BLIND_LABELS = {"TABLETOP", "EXTENSION_TABLETOP", "ISLAND_BODY", "DRAWER", "TRACK_SOCKET",
                   "SOCKET_MODULE", "PERSON", "HAND", "SINK", "CABINET_DOOR",
                   "ROCK_TABLE_LEG", "ACRYLIC_TABLE_LEG"}
# 每动作的"必需目标对象"契约（A1_READY 判定用；任一帧出现其一即满足基本可见）
REQUIRED_OBJECTS = {
    "EXTEND": ("TABLETOP", "EXTENSION_TABLETOP"),
    "RETRACT": ("TABLETOP", "EXTENSION_TABLETOP"),
    "DRAWER_OPEN": ("DRAWER", "UPPER_THIN_DRAWER"),
    "SOCKET_INSERT": ("TRACK_SOCKET", "SOCKET_MODULE"),
    "SOCKET_ADJUST": ("TRACK_SOCKET", "SOCKET_MODULE"),
}


def bbox_ok(bb, w, h) -> bool:
    return (len(bb) == 4 and 0 <= bb[0] < bb[2] <= w and 0 <= bb[1] < bb[3] <= h)


def load_rois():
    if ROI_FILE.exists():
        return json.loads(ROI_FILE.read_text(encoding="utf-8"))
    return {"annotation_version": "A1", "annotation_source": "L3_HUMAN_ROI",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reviewer": None, "annotations": []}


def save_rois(doc):
    doc["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = ROI_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ROI_FILE)


def refresh_state():
    """按 manifest 逐帧统计标注状态（框数/已标对象集）。"""
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rois = load_rois()["annotations"]
    by = {}
    for r in rois:
        by.setdefault((r["media_id"], r["frame_timestamp"]), []).append(r)
    cases = []
    for c in man["cases"]:
        fr = []
        for f in c["frames"]:
            key = (c["media_id"], f["t_s"])
            rs = by.get(key, [])
            fr.append({"frame": f["frame"], "t_s": f["t_s"], "sha256": f["sha256"],
                       "boxes": len(rs),
                       "objects": sorted({r["object_name"] for r in rs}),
                       "annotated": bool(rs)})
        cases.append({"media_id": c["media_id"], "requested": c["requested"],
                      "frames": fr,
                      "fully_annotated": all(x["annotated"] for x in fr if "error" not in x)})
    st = {"annotation_version": "A1", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "cases": cases}
    STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    return st


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/a3/screen":
            if A3_HTML.exists():
                self._send(200, A3_HTML.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"a3_screen.html missing", "text/plain")
            return
        if path == "/api/a3/candidates":
            if A3_CANDS_FILE.exists():
                self._send(200, A3_CANDS_FILE.read_bytes(), "application/json; charset=utf-8")
            else:
                self._json({"error": "候选未生成"})
            return
        if path == "/api/a3/screening":
            if A3_SCREEN_FILE.exists():
                self._send(200, A3_SCREEN_FILE.read_bytes(), "application/json; charset=utf-8")
            else:
                self._json({"verdicts": {}})
            return
        if path.startswith("/a3/thumbs/"):
            name = path.rsplit("/", 1)[-1]
            fp = _a3_thumbs_dir() / name
            if fp.exists():
                self._send(200, fp.read_bytes(), "image/jpeg")
                return
            self._send(404, b"thumb missing", "text/plain")
            return
        if path == "/a3/roi":
            if A3_ROI_HTML.exists():
                self._send(200, A3_ROI_HTML.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"a3_roi.html missing", "text/plain")
            return
        if path == "/api/a3/holdout":
            if A3_HOLDOUT_FILE.exists():
                self._send(200, A3_HOLDOUT_FILE.read_bytes(), "application/json; charset=utf-8")
            else:
                self._json({"error": "holdout 未冻结"})
            return
        if path == "/api/a3/rois":
            self._json(load_a3_rois())
            return
        if path == "/api/a3/blind":
            if A3_BLIND_FILE.exists():
                self._send(200, A3_BLIND_FILE.read_bytes(), "application/json; charset=utf-8")
            else:
                self._json({"error": "blind 未生成"})
            return
        if path == "/api/a3/blind-rois":
            self._json(load_a3_blind_rois())
            return
        if path.startswith("/a3/bframes/"):
            name = path.rsplit("/", 1)[-1]
            fp = A3_BLIND_FRAMES_DIR / name
            if fp.exists():
                self._send(200, fp.read_bytes(), "image/jpeg")
                return
            self._send(404, b"blind frame missing", "text/plain")
            return
        if path == "/a3/observability":
            if A3_OBS_HTML.exists():
                self._send(200, A3_OBS_HTML.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"observability html missing", "text/plain")
            return
        if path == "/api/a3/observability-human":
            self._json(load_a3_obs_human())
            return
        if path.startswith("/a3/hframes/"):
            name = path.rsplit("/", 1)[-1]
            fp = _a3_holdout_frames_dir() / name
            if fp.exists():
                self._send(200, fp.read_bytes(), "image/jpeg")
                return
            self._send(404, b"holdout frame missing", "text/plain")
            return
        if path == "/aux52":
            if AUX_HTML.exists():
                self._send(200, AUX_HTML.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"aux52.html missing", "text/plain")
            return
        if path == "/a21/bind":
            if A21_HTML.exists():
                self._send(200, A21_HTML.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"a21_bind.html missing", "text/plain")
            return
        if path == "/api/a21/binding":
            if A21_BIND_FILE.exists():
                self._send(200, A21_BIND_FILE.read_bytes(), "application/json; charset=utf-8")
            else:
                self._json({"media_ids": [52, 109], "bindings": []})
            return
        if path.startswith("/a21/frames/"):
            name = path.rsplit("/", 1)[-1]
            fp = _frames_dir() / name
            if fp.exists():
                self._send(200, fp.read_bytes(), "image/jpeg")
                return
            self._send(404, b"frame missing", "text/plain")
            return
        if path == "/api/aux52/candidates":
            aux = _aux_dir()
            items = []
            for fp in sorted(aux.glob("m52_aux_*.jpg")):
                items.append({"frame": fp.name, "bytes": fp.stat().st_size})
            sel = {}
            if AUX_SELECT_FILE.exists():
                sel = json.loads(AUX_SELECT_FILE.read_text(encoding="utf-8"))
            self._json({"window": [7.5, 10.0], "step_s": 0.25, "candidates": items,
                        "selection": sel.get("chosen", []), "media_id": 52})
            return
        if path.startswith("/aux52/frames/"):
            name = path.rsplit("/", 1)[-1]
            fp = _aux_dir() / name
            if fp.exists():
                self._send(200, fp.read_bytes(), "image/jpeg")
                return
            self._send(404, b"aux frame missing", "text/plain")
            return
        if path == "/api/manifest":
            self._send(200, MANIFEST.read_bytes(), "application/json; charset=utf-8")
            return
        if path == "/api/rois":
            self._json(load_rois())
            return
        if path == "/api/state":
            self._json(refresh_state())
            return
        if path == "/api/labels":
            self._json({"labels": LABELS})
            return
        if path.startswith("/frames/"):
            name = path.rsplit("/", 1)[-1]
            man = json.loads(MANIFEST.read_text(encoding="utf-8"))
            hit = next((f["local_path"] for c in man["cases"] for f in c["frames"]
                        if f.get("frame") == name), None)
            if hit and Path(hit).exists():
                data = Path(hit).read_bytes()
                self._send(200, data, "image/jpeg")
                return
            self._send(404, b"frame missing", "text/plain")
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        ln = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(ln) if ln else b""
        if self.path == "/api/a21/binding":
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json({"ok": False, "error": "bad json"}, 400)
                return
            mid = data.get("media_id")
            t_s = data.get("t_s")
            idx = data.get("chosen_index")
            if mid not in (52, 109) or not isinstance(t_s, (int, float)):
                self._json({"ok": False, "error": "media_id 须 52/109 且 t_s 数字"}, 400)
                return
            if idx is not None and not isinstance(idx, int):
                self._json({"ok": False, "error": "chosen_index 须整数或 null"}, 400)
                return
            doc = {"media_ids": [52, 109], "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "bindings": []}
            if A21_BIND_FILE.exists():
                doc = json.loads(A21_BIND_FILE.read_text(encoding="utf-8"))
            doc["bindings"] = [b for b in doc.get("bindings", [])
                               if not (b["media_id"] == mid and b["t_s"] == t_s)]
            doc["bindings"].append({"media_id": mid, "t_s": float(t_s),
                                    "chosen_index": idx,
                                    "at": time.strftime("%Y-%m-%d %H:%M:%S")})
            tmp = A21_BIND_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(A21_BIND_FILE)
            self._json({"ok": True, "bindings": len(doc["bindings"])})
            return
        if self.path == "/api/a3/verdict":
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json({"ok": False, "error": "bad json"}, 400)
                return
            mid = data.get("media_id")
            label = data.get("label")
            if label not in ("YES_EXTEND", "NO_EXTEND", "UNCLEAR"):
                self._json({"ok": False, "error": "label 须 YES_EXTEND/NO_EXTEND/UNCLEAR"}, 400)
                return
            doc = {"verdicts": {}}
            if A3_SCREEN_FILE.exists():
                doc = json.loads(A3_SCREEN_FILE.read_text(encoding="utf-8"))
            doc["verdicts"][str(mid)] = {"label": label,
                                         "note": data.get("note", ""),
                                         "at": time.strftime("%Y-%m-%d %H:%M:%S")}
            doc["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            tmp = A3_SCREEN_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(A3_SCREEN_FILE)
            self._json({"ok": True, "media_id": mid, "label": label})
            return
        if self.path == "/api/a3/rois/save":
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json({"ok": False, "error": "bad json"}, 400)
                return
            mid = data.get("media_id")
            t_s = data.get("frame_timestamp")
            rois_in = data.get("rois") or []
            man = json.loads(A3_HOLDOUT_FILE.read_text(encoding="utf-8"))
            case = next((c for c in man["cases"] if c["media_id"] == mid), None)
            frame = next((f for f in (case or {}).get("frames", []) if f["t_s"] == t_s), None)
            if case is None or frame is None:
                self._json({"ok": False, "error": "unknown holdout media/frame"}, 404)
                return
            doc = load_a3_rois()
            doc["annotations"] = [a for a in doc["annotations"]
                                  if not (a["media_id"] == mid and a["frame_timestamp"] == t_s)]
            w, h = frame["width"], frame["height"]
            for r in rois_in:
                bb = [float(v) for v in r.get("bbox_pixel", [])]
                if not bbox_ok(bb, w, h):
                    self._json({"ok": False, "error": f"bbox 越界/非法: {bb} (frame {w}x{h})"}, 400)
                    return
                doc["annotations"].append({
                    "case_id": case["case_id"], "media_id": mid,
                    "window_id": f"W{case['frozen_window_s'][0]}-{case['frozen_window_s'][1]}",
                    "frame_timestamp": t_s, "frame": frame["frame"],
                    "frame_hash": frame["sha256"],
                    "object_name": r.get("object_name"),
                    "bbox_pixel": [int(v) for v in bb],
                    "bbox_normalized": [round(bb[0] / w, 4), round(bb[1] / h, 4),
                                        round(bb[2] / w, 4), round(bb[3] / h, 4)],
                    "annotation_source": "L3_HUMAN_ROI", "reviewer": doc.get("reviewer"),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "annotation_version": "A3"})
            save_a3_rois(doc)
            self._json({"ok": True, "saved": len(rois_in), "frame": frame["frame"]})
            return
        if self.path == "/api/a3/observability/save":
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json({"ok": False, "error": "bad json"}, 400)
                return
            answers_in = data.get("answers") or []
            by_id = {}
            for a in answers_in:
                oid = a.get("opaque_case_id")
                lab = a.get("observability_label")
                if oid not in ("H001", "H002", "H003", "H004", "H005", "H006"):
                    self._json({"ok": False, "error": f"未知案例: {oid}"}, 400)
                    return
                if lab not in OBS_LABELS:
                    self._json({"ok": False, "error": f"判断值非法: {lab}"}, 400)
                    return
                by_id[oid] = a
            missing = [f"H{i:03d}" for i in range(1, 7) if f"H{i:03d}" not in by_id]
            if missing:
                self._json({"ok": False, "error": f"还有 {len(missing)} 个案例未完成审核：{','.join(missing)}"}, 400)
                return
            doc = {"experiment": "MMVV_A3_OBSERVABILITY_HUMAN_V1", "review_version": "V1",
                   "reviewed_at": time.strftime("%Y-%m-%d %H:%M:%S"), "answers": [],
                   "done": 6}
            for oid in [f"H{i:03d}" for i in range(1, 7)]:
                a = by_id[oid]
                doc["answers"].append({
                    "opaque_case_id": oid,
                    "observability_label": a.get("observability_label"),
                    "human_note": (a.get("human_note") or "").strip()[:500],
                    "reviewed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "review_version": "V1"})
            save_a3_obs_human(doc)
            self._json({"ok": True, "saved": 6, "file": A3_OBS_HUMAN_FILE.name})
            return
        if self.path == "/api/a3/blind-rois/save":
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json({"ok": False, "error": "bad json"}, 400)
                return
            oid = data.get("opaque_case_id")
            t_s = data.get("frame_timestamp")
            rois_in = data.get("rois") or []
            man = json.loads(A3_BLIND_FILE.read_text(encoding="utf-8"))
            case = next((c for c in man["cases"] if c["opaque_case_id"] == oid), None)
            frame = next((f for f in (case or {}).get("frames", []) if f["t_s"] == t_s), None)
            if case is None or frame is None:
                self._json({"ok": False, "error": "unknown blind case/frame"}, 404)
                return
            doc = load_a3_blind_rois()
            doc["annotations"] = [a for a in doc["annotations"]
                                  if not (a["opaque_case_id"] == oid and a["frame_timestamp"] == t_s)]
            w, h = frame["width"], frame["height"]
            for r in rois_in:
                obj = r.get("object_name")
                if obj not in A3_BLIND_LABELS:
                    self._json({"ok": False, "error": f"对象不在允许集: {obj}"}, 400)
                    return
                bb = [float(v) for v in r.get("bbox_pixel", [])]
                if not bbox_ok(bb, w, h):
                    self._json({"ok": False, "error": f"bbox 越界/非法: {bb} (frame {w}x{h})"}, 400)
                    return
                doc["annotations"].append({
                    "opaque_case_id": oid,
                    "window_id": f"W{case['frozen_window_s'][0]}-{case['frozen_window_s'][1]}",
                    "frame_timestamp": t_s, "frame": frame["frame"],
                    "frame_hash": frame["sha256"],
                    "object_name": obj,
                    "bbox_pixel": [int(v) for v in bb],
                    "bbox_normalized": [round(bb[0] / w, 4), round(bb[1] / h, 4),
                                        round(bb[2] / w, 4), round(bb[3] / h, 4)],
                    "annotation_source": "L3_HUMAN_ROI", "reviewer": doc.get("reviewer"),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "annotation_version": "A3_BLIND"})
            save_a3_blind_rois(doc)
            self._json({"ok": True, "saved": len(rois_in), "frame": frame["frame"]})
            return
        if self.path == "/api/aux52/select":
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json({"ok": False, "error": "bad json"}, 400)
                return
            role = data.get("role")
            t_s = data.get("t_s")
            if role not in ("AUX1", "AUX2") or not isinstance(t_s, (int, float)):
                self._json({"ok": False, "error": "role 须为 AUX1/AUX2 且 t_s 为数字"}, 400)
                return
            aux = _aux_dir()
            hit = next((fp for fp in aux.glob("m52_aux_*.jpg")
                        if abs(float(fp.stem.replace("m52_aux_", "").replace("_", ".")) - float(t_s)) < 1e-6), None)
            if hit is None:
                self._json({"ok": False, "error": f"候选不存在 t_s={t_s}"}, 404)
                return
            doc = {"media_id": 52, "window": [7.5, 10.0],
                   "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "chosen": []}
            if AUX_SELECT_FILE.exists():
                doc = json.loads(AUX_SELECT_FILE.read_text(encoding="utf-8"))
            doc["chosen"] = [c for c in doc.get("chosen", []) if c.get("role") != role]
            doc["chosen"].append({"role": role, "t_s": float(t_s), "frame": hit.name,
                                  "selected_by": "ARCHITECT", "at": time.strftime("%Y-%m-%d %H:%M:%S")})
            tmp = AUX_SELECT_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(AUX_SELECT_FILE)
            self._json({"ok": True, "chosen": doc["chosen"]})
            return
        if self.path == "/api/rois/save":
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self._json({"ok": False, "error": "bad json"}, 400)
                return
            mid = data.get("media_id")
            t_s = data.get("frame_timestamp")
            rois_in = data.get("rois") or []
            man = json.loads(MANIFEST.read_text(encoding="utf-8"))
            case = next((c for c in man["cases"] if c["media_id"] == mid), None)
            frame = next((f for f in (case or {}).get("frames", []) if f["t_s"] == t_s), None)
            if case is None or frame is None:
                self._json({"ok": False, "error": "unknown media/frame"}, 404)
                return
            doc = load_rois()
            doc["annotations"] = [a for a in doc["annotations"]
                                  if not (a["media_id"] == mid and a["frame_timestamp"] == t_s)]
            w, h = frame["width"], frame["height"]
            for r in rois_in:
                bb = [float(v) for v in r.get("bbox_pixel", [])]
                if not bbox_ok(bb, w, h):
                    self._json({"ok": False, "error": f"bbox 越界/非法: {bb} (frame {w}x{h})"}, 400)
                    return
                doc["annotations"].append({
                    "media_id": mid, "window_id": f"W{case['frozen_window_s'][0]}-{case['frozen_window_s'][1]}",
                    "frame_timestamp": t_s, "frame_hash": frame["sha256"],
                    "object_name": r.get("object_name"),
                    "bbox_pixel": [int(v) for v in bb],
                    "bbox_normalized": [round(bb[0] / w, 4), round(bb[1] / h, 4),
                                        round(bb[2] / w, 4), round(bb[3] / h, 4)],
                    "annotation_source": "L3_HUMAN_ROI", "reviewer": doc.get("reviewer"),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "annotation_version": "A1"})
            save_rois(doc)
            refresh_state()
            self._json({"ok": True, "saved": len(rois_in), "frame": frame["frame"]})
            return
        self._json({"ok": False, "error": "unknown post"}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8933)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"MMVV A1 标注台 @ http://{a.host}:{a.port}  (ROI -> {ROI_FILE})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
