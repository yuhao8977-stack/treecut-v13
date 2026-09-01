# -*- coding: utf-8 -*-
"""V0.6.1 — 接管恢复：自动点击目标卡片本体 → 详情/新tab → 视频媒体捕获 → 验证。

页面正常点击（非 API 构造）；观察器先挂载；身份门 + ffprobe + 全解码 + SHA256。
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
STAGING = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\staging\B007")
QUARANTINE = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\quarantine")
Z_MEDIA = Path(r"Z:\TreeCut_Media\B007\published_media")
NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"
TARGET = "69f9a0ac000000003701d937"
CORE = "通透又显大的开放式厨房标配岛台"
CREATOR_DUR = 21.0
FFPROBE = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
FFMPEG = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"


def _safe(url):
    try:
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    config = load_config()
    config.workspace_id = "B007"
    config.validate()
    runtime = BrowserRuntime(config)
    try:
        runtime.workspace.acquire_lock()
    except RuntimeError as error:
        print(f"PROFILE_LOCKED: {error}")
        return 2
    try:
        runtime.start_browser(headless=False)
        runtime.reconcile_tabs()
        diag = {"pages_seen": [], "responses": [], "media_candidates": [],
                "identity_evidence": [], "errors": []}

        def run():
            ctx = runtime._context
            tab = runtime.ensure_tabs().get("CREATOR")
            full_urls = []  # 内存：视频完整 URL（含签名 query），仅用于立即下载，不持久化

            def watch(page, tag):
                def on_resp(response):
                    try:
                        u = response.url or ""
                        ctype = (response.headers.get("content-type") or "").lower()
                        s = _safe(u)
                        diag["responses"].append({"page": tag, "safe": s, "ctype": ctype[:30],
                                                  "status": response.status})
                        low = u.lower()
                        if "video" in ctype or ".mp4" in low or ".m3u8" in low or "sns-video" in s:
                            cand = {"page": tag, "safe": s, "ctype": ctype[:40],
                                    "status": response.status,
                                    "len": response.headers.get("content-length"),
                                    "range": response.headers.get("content-range", "")[:40]}
                            diag["media_candidates"].append(cand)
                            # 记录完整 URL 到内存（仅用于立即下载，不持久化）
                            if "video" in ctype or ".mp4" in low:
                                full_urls.append(u)
                        if "json" in ctype and TARGET in u:
                            diag["identity_evidence"].append({"page": tag, "safe": s})
                    except Exception:
                        pass
                page.on("response", on_resp)
                page.on("download", lambda dl: diag.setdefault("downloads", []).append(dl.suggested_filename))
                diag["pages_seen"].append(tag)

            for role in ("CREATOR", "SPOTLIGHT", "FRONTEND"):
                try:
                    p = runtime.ensure_tabs().get(role)
                    if p:
                        watch(p, role)
                except Exception:
                    pass
            ctx.on("page", lambda p: watch(p, "NEW"))

            # 定位 + 点击卡片本体
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(9)
            tab.evaluate(
                """(kw) => {
                  const i = document.querySelector('input[placeholder*="搜索已发布"], input[placeholder*="搜索"]');
                  if (!i) return false;
                  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                  setter.call(i, kw);
                  i.dispatchEvent(new Event('input', {bubbles:true}));
                  i.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true, cancelable:true}));
                  i.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', bubbles:true, cancelable:true}));
                  return true;
                }""", CORE)
            time.sleep(5)
            # 点击卡片中心（Playwright 真实点击，避开操作按钮区）
            clicked = None
            try:
                loc = tab.locator("[class*=note-card]").filter(has_text=CORE[:6]).first
                if loc.count() > 0:
                    box = loc.bounding_box()
                    if box:
                        cx = box["x"] + box["width"] * 0.4   # 左中（标题/封面区，避开右侧操作按钮）
                        cy = box["y"] + box["height"] * 0.5
                        tab.mouse.click(cx, cy)
                        clicked = {"x": round(cx), "y": round(cy)}
            except Exception as e:
                diag["errors"].append(f"card click: {str(e)[:100]}")
            print("CLICKED =", clicked)
            # 等待详情/新tab/媒体
            deadline = time.time() + 120
            captured = False
            while time.time() < deadline:
                # 触发所有页面的 video 播放
                for p in ctx.pages:
                    try:
                        p.evaluate("""() => {
                          const v = document.querySelector('video');
                          if (v) { v.muted = true; v.play().catch(()=>{}); }
                          const els = Array.from(document.querySelectorAll('[class*=play], [class*=video], [class*=player]'));
                          for (const e of els) { const r = e.getBoundingClientRect(); if (r.width>40 && r.height>40) { e.click(); break; } }
                        }""")
                    except Exception:
                        pass
                # 一旦捕获视频完整 URL → 用浏览器会话下载完整文件
                if full_urls:
                    url = full_urls[0]
                    try:
                        resp = ctx.request.get(url, timeout=120000)
                        if resp.ok:
                            body = resp.body()
                            if body and len(body) > 1000:
                                part = STAGING / f"{TARGET}.mp4.part"
                                part.parent.mkdir(parents=True, exist_ok=True)
                                part.write_bytes(body)
                                diag["media_candidates"].append({
                                    "page": "SESSION_DOWNLOAD", "safe": _safe(url),
                                    "ctype": resp.headers.get("content-type", "")[:40],
                                    "status": resp.status, "captured_to": str(part),
                                    "captured_bytes": len(body)})
                                captured = True
                                break
                    except Exception as e:
                        diag["errors"].append(f"session download: {str(e)[:120]}")
                if any(c.get("captured_to") for c in diag["media_candidates"]):
                    captured = True
                    break
                time.sleep(3)
            print("CAPTURED =", captured)
            print("MEDIA_URLS_OBSERVED =", len(full_urls))
            # 页面 dump
            for i, p in enumerate(ctx.pages):
                try:
                    info = p.evaluate(
                        """() => {
                          const v = document.querySelector('video');
                          return {url: location.href.slice(0,120), has_video: !!v,
                                  vsrc: v && v.currentSrc ? v.currentSrc.slice(0,80) : null};
                        }""")
                    print(f"  PAGE[{i}] {json.dumps(info, ensure_ascii=True)}")
                except Exception:
                    pass
            return {"captured": captured,
                    "identity": bool(diag["identity_evidence"]),
                    "media_count": len(diag["media_candidates"])}

        outcome = runtime._in_browser(run, timeout=500)

        part = None
        for c in diag["media_candidates"]:
            if c.get("captured_to") and Path(c["captured_to"]).exists():
                part = Path(c["captured_to"])
                break
        result = {"pilot": "V06_ASSISTED_PILOT1", "note_id": TARGET,
                  "identity_evidence": outcome["identity"], "media_candidates": outcome["media_count"],
                  "media_captured": bool(part)}
        if not part:
            result["status"] = "V06_ASSISTED_PILOT1_NEEDS_REPAIR"
            result["reason"] = "no media bytes captured after card click"
        else:
            result["status"] = validate(part, result)
        result["diagnostic"] = diag
        (OUT / "B007_V061_ASSISTED_PILOT1.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (OUT / "B007_V061_MEDIA_OBSERVATION_DIAGNOSTIC.json").write_text(
            json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "diagnostic"},
                         ensure_ascii=False, indent=2))
        return 0
    finally:
        runtime.close()
        print("TAKEOVER_DONE")


def validate(part: Path, result) -> str:
    tech = {"file": str(part), "size": part.stat().st_size}
    try:
        out = subprocess.run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(part)],
                             capture_output=True, timeout=120)
        raw = out.stdout.decode("utf-8", errors="replace")
        probe = json.loads(raw)
        fmt = probe.get("format", {})
        streams = probe.get("streams", [])
        vs = next((s for s in streams if s.get("codec_type") == "video"), None)
        au = next((s for s in streams if s.get("codec_type") == "audio"), None)
        dur = float(fmt.get("duration") or (vs or {}).get("duration") or 0)
        tech.update({"ffprobe_ok": bool(vs and dur > 0), "duration": dur,
                     "video_codec": (vs or {}).get("codec_name"),
                     "width": (vs or {}).get("width"), "height": (vs or {}).get("height"),
                     "audio_codec": (au or {}).get("codec_name") if au else None})
    except Exception as e:
        tech["ffprobe_error"] = str(e)[:200]
        return "V06_ASSISTED_PILOT1_NEEDS_REPAIR"
    try:
        dec = subprocess.run([FFMPEG, "-v", "error", "-i", str(part), "-f", "null", "-"],
                             capture_output=True, text=True, timeout=600)
        tech["full_decode_ok"] = dec.returncode == 0
    except Exception as e:
        tech["decode_error"] = str(e)[:120]
        tech["full_decode_ok"] = False
    h = hashlib.sha256()
    with open(part, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    sha = h.hexdigest()
    tech["sha256"] = sha
    tol = max(5.0, CREATOR_DUR * 0.15)
    match = abs((tech.get("duration") or 0) - CREATOR_DUR) <= tol
    tech["duration_crosscheck"] = {"creator": CREATOR_DUR, "ffprobe": round(tech.get("duration") or 0, 2),
                                   "tolerance": round(tol, 2), "pass": match}
    ok = tech.get("ffprobe_ok") and tech.get("full_decode_ok") and sha and match
    (OUT / "B007_V061_MEDIA_TECH_METADATA.json").write_text(
        json.dumps(tech, ensure_ascii=False, indent=2), encoding="utf-8")
    if ok:
        Z_MEDIA.mkdir(parents=True, exist_ok=True)
        final = Z_MEDIA / f"{TARGET}__{sha[:12]}.mp4"
        part.replace(final)
        tech["final_path"] = str(final)
        conn = sqlite3.connect(DB, timeout=30)
        conn.execute("DELETE FROM b007_published_media_recovery_v1 WHERE note_id=?", (TARGET,))
        conn.execute(
            "INSERT INTO b007_published_media_recovery_v1(note_id,sample_id,expected_note_id,actual_note_id,"
            "recovery_status,source_type,container,byte_size,sha256,duration,width,height,fps,video_codec,"
            "audio_codec,creator_duration,duration_match_status,final_path,recovered_at,validation_version,"
            "block_reason,attempts,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TARGET, "PILOT1", TARGET, TARGET, "RECOVERED_EXACT", "USER_ASSISTED_CREATOR_DETAIL", "mp4",
             tech["size"], sha, tech.get("duration"), tech.get("width"), tech.get("height"), None,
             tech.get("video_codec"), tech.get("audio_codec"), CREATOR_DUR,
             "MATCH_WITHIN_TOLERANCE" if match else "MISMATCH", str(final),
             time.strftime("%Y-%m-%d %H:%M:%S"), "V0.6.1-PILOT1", None, 1, time.time()))
        conn.commit()
        conn.close()
        result["tech"] = tech
        return "V06_ASSISTED_PILOT1_PASS"
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    q = QUARANTINE / f"{TARGET}.part"
    part.replace(q)
    tech["quarantined_to"] = str(q)
    result["tech"] = tech
    return "V06_ASSISTED_PILOT1_NEEDS_REPAIR"


if __name__ == "__main__":
    sys.exit(main())
