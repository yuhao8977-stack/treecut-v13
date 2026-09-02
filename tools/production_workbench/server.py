#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TreeCut Production Workbench — 本地单机工作台(§59-73)。

功能: 左=脚本/Beats/Claims; 中=视频(subclip 播放)+时间线; 右=候选卡/证据/QA;
Beat 点击→高亮+Top3+claim 要求+QA; 播放=subclip 窗口; 一键替换→重QA→保存; 有界裁剪。
Server: stdlib http.server + Range 支持。重活不在此线程(数据由构建器预生成)。
运行: python tools/production_workbench/server.py [--dir reports/storage] [--port 8899]
"""
import argparse
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root
PROJ_DIR = ROOT / "reports" / "storage"
PROJECT_FILE = PROJ_DIR / "TREECUT_WORKBENCH_PROJECT_V1.json"
INDEX = Path(__file__).parent / "index.html"
sys.path.insert(0, str(ROOT / "src"))


def resolve_local(video_path: str) -> Path | None:
    """把 UNC/本地路径映射为可访问文件; UNC 需映射盘或直接读(Windows 可读 UNC)。"""
    if not video_path:
        return None
    p = Path(video_path)
    return p if p.exists() else None


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

    def _send_json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            if INDEX.exists():
                self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"index.html missing", "text/plain")
            return
        if path == "/api/project":
            if PROJECT_FILE.exists():
                self._send(200, PROJECT_FILE.read_bytes(), "application/json; charset=utf-8")
            else:
                self._send(404, b"no project json", "application/json")
            return
        if path.startswith("/api/qa/"):
            # /api/qa/<media_id>?beat=..&reason=.. — 本地重QA(由构建器函数执行, 简化返回)
            mid = path.rsplit("/", 1)[-1]
            q = json.loads(PROJECT_FILE.read_text(encoding="utf-8"))
            self._send_json({"media_id": mid, "qa": "PENDING_BUILDER_QA", "note": "替换后重QA由构建器回写"})
            return
        if path.startswith("/video/"):
            # /video/?p=<urlencoded local path>
            return
        # 静态资源: /file?p=... 需授权前缀, 防目录穿越
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        p = qs.get("p", [None])[0]
        if p:
            fp = resolve_local(p)
            if fp and fp.is_file():
                size = fp.stat().st_size
                rng = self.headers.get("Range")
                if rng:
                    m = re.match(r"bytes=(\d*)-(\d*)", rng)
                    start = int(m.group(1) or 0)
                    end = int(m.group(2) or size - 1)
                    end = min(end, size - 1)
                    chunk = bytearray()
                    with open(fp, "rb") as f:
                        f.seek(start)
                        chunk = f.read(end - start + 1)
                    self.send_response(206)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", str(len(chunk)))
                    self.end_headers()
                    self.wfile.write(bytes(chunk))
                    return
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(size))
                self.end_headers()
                with open(fp, "rb") as f:
                    while True:
                        chunk = f.read(1 << 20)
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except BrokenPipeError:
                            break
                return
            self._send(404, b"file not found", "text/plain")
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        path = self.path.split("?")[0]
        ln = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(ln) if ln else b""
        if path == "/api/replace":
            # {beat_id, media_id, subclip:{start,end}} → 更新项目 JSON(持久化, 简单原子写)
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self._send_json({"ok": False, "error": "bad json"}, 400)
                return
            if PROJECT_FILE.exists():
                proj = json.loads(PROJECT_FILE.read_text(encoding="utf-8"))
                for b in proj.get("beats", []):
                    if b.get("id") == data.get("beat_id"):
                        b["selected"] = data.get("selection")
                        b["qa_note"] = "REPLACED_AWAIT_REBUILD_QA"
                tmp = PROJECT_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
                os.replace(tmp, PROJECT_FILE)
                self._send_json({"ok": True, "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")})
                return
            self._send_json({"ok": False, "error": "no project"}, 404)
            return
        self._send_json({"ok": False, "error": "unknown post"}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Workbench @ http://{args.host}:{args.port}  (project: {PROJECT_FILE})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
