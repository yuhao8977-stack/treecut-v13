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

LABELS = ["TABLETOP", "EXTENSION_TABLETOP", "DRAWER", "UPPER_THIN_DRAWER", "TRACK_SOCKET",
          "SOCKET_MODULE", "PERSON", "HAND", "ISLAND_BODY", "OTHER_MOVING_PART"]
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
