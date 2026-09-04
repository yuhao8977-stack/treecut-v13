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

# Source Audit R1 P1: /file 只允许素材/工作根（防任意路径读取/目录穿越）。
# 候选路径通常来自: X1 素材盘(UNC)、E 运行时工作目录、reports/storage(项目/帧证据)。
ALLOWED_ROOTS = [
    Path(r"\\X1\素材盘01"),
    Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime"),
    Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data"),
    PROJ_DIR,
]


def _norm(p: Path) -> str:
    try:
        return os.path.normcase(str(p.resolve()))
    except OSError:
        return os.path.normcase(str(p))


def resolve_local(video_path: str) -> Path | None:
    """把本地路径映射为可访问文件；仅允许 ALLOWED_ROOTS 内（防目录穿越/任意读）。
    服务器必须保持 127.0.0.1 监听，不得改为局域网/公网。"""
    if not video_path:
        return None
    p = Path(video_path)
    if not p.exists() or not p.is_file():
        return None
    rp = _norm(p)
    for root in ALLOWED_ROOTS:
        if rp.startswith(_norm(root) + os.sep) or rp == _norm(root):
            return p
    return None


def _probe_duration(path: str) -> float | None:
    """ffprobe 取源时长（trim 边界校验用）；失败返回 None。"""
    import subprocess
    ffp = Path(r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe")
    if not ffp.exists():
        return None
    try:
        out = subprocess.run([str(ffp), "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", path], capture_output=True, timeout=60)
        return float(out.stdout.decode("utf-8", errors="replace").strip())
    except Exception:
        return None


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
        if path in ("/api/replace", "/api/trim", "/api/reqa"):
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self._send_json({"ok": False, "error": "bad json"}, 400)
                return
            if not PROJECT_FILE.exists():
                self._send_json({"ok": False, "error": "no project"}, 404)
                return
            proj = json.loads(PROJECT_FILE.read_text(encoding="utf-8"))
            beat_id = data.get("beat_id")
            beat = next((b for b in proj.get("beats", []) if b.get("id") == beat_id), None)
            if beat is None:
                self._send_json({"ok": False, "error": "no beat"}, 404)
                return
            if path == "/api/replace":
                # Source Audit R1.1: media_id 必须∈本 beat candidates，否则 400 INVALID_CANDIDATE；
                # 不得拿旧 selected 元数据配新 media_id。
                sel_in = data.get("selection") or {}
                cand = next((c for c in (beat.get("candidates") or [])
                             if str(c.get("media_id")) == str(sel_in.get("media_id"))), None)
                if cand is None:
                    self._send_json({"ok": False,
                                     "error": f"INVALID_CANDIDATE: media_id={sel_in.get('media_id')} 不在本 beat candidates"},
                                    400)
                    return
                base = dict(cand)  # 以目标候选元数据为基底，保留 actions/object/eligible/evidence/path/... 
                base["media_id"] = sel_in.get("media_id")
                if "subclip" in sel_in:
                    base["subclip"] = sel_in["subclip"]
                beat["selected"] = base
            elif path == "/api/trim":
                sel = beat.get("selected") or {}
                cand = next((c for c in (beat.get("candidates") or [])
                             if str(c.get("media_id")) == str(sel.get("media_id"))), None)
                src_path = (cand or sel or {}).get("path")
                start = float(data.get("start_s", (sel.get("subclip") or {}).get("start_s", 0)))
                end = float(data.get("end_s", (sel.get("subclip") or {}).get("end_s", 0)))
                # Source Audit R1 P1: 真边界校验（原实现只 max(0,start)，称"有界"名不副实）
                if not (0.0 <= start < end):
                    self._send_json({"ok": False, "error": f"非法区间 start={start} end={end} (需 0<=start<end)"}, 400)
                    return
                dur = _probe_duration(src_path) if src_path else None
                if dur is not None and end > dur + 0.05:
                    self._send_json({"ok": False, "error": f"end={end} 超出源时长 {dur:.3f}s"}, 400)
                    return
                if dur is None:
                    self._send_json({"ok": False,
                                     "error": "无法探测源时长（缺 path 或 ffprobe）——禁止无界裁剪，请先回填 path"},
                                    400)
                    return
                # Source Audit R1.1: 动作型镜头必须保留动作证据窗（trim 不得裁掉动作）
                a0 = (cand or sel or {}).get("action_start_s")
                a1 = (cand or sel or {}).get("action_end_s")
                if a0 is None:
                    a0 = ((sel.get("subclip") or {}).get("action_start_s"))
                if a1 is None:
                    a1 = ((sel.get("subclip") or {}).get("action_end_s"))
                if a0 is not None and a1 is not None and (start > float(a0) + 1e-6 or end < float(a1) - 1e-6):
                    self._send_json({"ok": False,
                                     "error": f"ACTION_EVIDENCE_TRIMMED_OUT: 动作窗 [{a0},{a1}] 需被 trim 覆盖"
                                              f" (trim=[{start},{end}])；人工 override 流程未实现，请调整区间"},
                                    400)
                    return
                sub = dict(sel.get("subclip") or {})
                sub["start_s"] = round(start, 3)
                sub["end_s"] = round(end, 3)
                sel["subclip"] = sub
                beat["selected"] = sel
            # 本机基础重QA(无 qwen/推理; 诚实本地规则)
            qa = local_reqa(proj, beat)
            beat["qa_note"] = "OK" if not any(r["status"] == "FAIL" for r in qa) else "FAIL"
            beat["qa_local"] = qa
            tmp = PROJECT_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, PROJECT_FILE)
            self._send_json({"ok": True, "qa": qa,
                             "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")})
            return
        self._send_json({"ok": False, "error": "unknown post"}, 404)


def local_reqa(proj: dict, beat: dict) -> list[dict]:
    """本机基础 QA(无 qwen): 资格字段(项目内候选携带) + claim 动作匹配 + 重复 + 配置(字幕/音/BGM)。
    诚实标注 LOCAL_RULE；完整 QA 由 builder/ProductionQAService 在重建时执行。"""
    import sys as _s
    _s.path.insert(0, str(ROOT / "src"))
    out = []
    claim = beat.get("claim") or {}
    sel = beat.get("selected")
    req_act = claim.get("required_action")
    if not sel:
        out.append({"gate": "SEMANTIC", "key": "CLAIM_SUPPORTED", "status": "FAIL",
                    "detail": "本 beat 未选候选 → UNSUPPORTED_CORE_CLAIM(需人工选镜或换检索)"})
        return out
    cand_actions = sel.get("actions") or []
    if req_act and req_act not in cand_actions:
        out.append({"gate": "SEMANTIC", "key": "ACTION_DEMONSTRATED", "status": "FAIL",
                    "detail": f"claim 需 {req_act}, 候选动作={cand_actions} → WRONG_ACTION"})
    else:
        out.append({"gate": "SEMANTIC", "key": "ACTION_DEMONSTRATED", "status": "PASS",
                    "detail": f"claim {req_act} ∈ 候选动作"})
    # 重复: 同 media 已被其它 beat 选走
    mids = [(b.get("selected") or {}).get("media_id") for b in proj.get("beats", []) if b.get("id") != beat.get("id")]
    if sel.get("media_id") in mids:
        out.append({"gate": "PRODUCTION", "key": "NEAR_DUPLICATE_FREE", "status": "FAIL",
                    "detail": "该 media 已在其它 beat 使用 → MAJOR_DUPLICATE(叙事近重由 builder 全量重算)"})
    else:
        out.append({"gate": "PRODUCTION", "key": "NEAR_DUPLICATE_FREE", "status": "PASS", "detail": ""})
    # Source Audit R1.1: 配置期望 ≠ 成片实测——非观测事实不得冒充 PASS/完整 QA
    out.append({"gate": "TECHNICAL", "key": "CAPTION_SIZE", "status": "WARNING",
                "detail": "CONFIG_EXPECTED: 渲染默认 66(62-68) 由渲染侧保证，非本成片实测（完整 QA 由 ProductionQAService 重建时执行）"})
    out.append({"gate": "TECHNICAL", "key": "VOICE_PROVIDER_VALID", "status": "WARNING",
                "detail": "SAPI=FALLBACK; 真人音 VOICE_INPUT_REQUIRED"})
    out.append({"gate": "PRODUCTION", "key": "BGM_PRESENT_IF_REQUIRED", "status": "WARNING",
                "detail": "BGM_LIBRARY_NOT_READY(无授权音乐)"})
    out.append({"gate": "LOCAL_RULE", "key": "NOTE", "status": "WARNING",
                "detail": "本 QA 为 UI 本地规则; AV/响度/烧录等完整 QA 由 ProductionQAService 重建时执行"})
    return out


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
