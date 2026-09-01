# -*- coding: utf-8 -*-
"""V0.6.1 — USER-ASSISTED CREATOR DETAIL PUBLISHED MEDIA RECOVERY PILOT1。

用户唯一动作：在 Creator 笔记管理中正常点开目标笔记详情。
TreeCut：先挂载观察器 → 显示提示 → 等待用户点击 → 身份门 → 捕获页面自有媒体响应
→ staging .part → ffprobe + ffmpeg full decode + SHA256 → duration crosscheck → Z / quarantine。
不切前台账号；不批量；无凭证持久化。
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
REPO = Path(r"C:\Users\admin\github\treecut-v13")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
STAGING = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\staging\B007")
QUARANTINE = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\quarantine")
Z_MEDIA = Path(r"Z:\TreeCut_Media\B007\published_media")

# Pilot1 样本：C 组 2026-05（近期可寻、付费高效率候选、有 creator duration）
PILOT_NOTE = "69f9a0ac000000003701d937"
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

        # 样本信息
        manifest = json.loads((OUT / "B007_SAMPLE20_V1.json").read_text(encoding="utf-8"))
        sample = next(s for s in manifest["samples"] if s["note_id"] == PILOT_NOTE)
        creator_duration = sample["duration"]
        title = sample.get("title") or ""

        diag = {"media_candidates": [], "identity_evidence": [], "responses": [],
                "pages_seen": [], "downloads": [], "errors": []}

        def run():
            context = runtime._context
            tab = runtime.ensure_tabs().get("CREATOR")

            def safe_print(s):
                try:
                    print(s)
                except UnicodeEncodeError:
                    print(str(s).encode("gbk", errors="replace").decode("gbk"))

            # ========== 先挂载观察器（用户点击之前） ==========
            def watch_page(page, tag):
                def on_resp(response):
                    try:
                        u = response.url or ""
                        ctype = (response.headers.get("content-type") or "").lower()
                        s = _safe(u)
                        diag["responses"].append({"page": tag, "safe": s, "ctype": ctype[:30],
                                                  "status": response.status})
                        low = u.lower()
                        is_video = "video" in ctype or ".mp4" in low or ".m3u8" in low or "sns-video" in s
                        if is_video:
                            cand = {"page": tag, "safe": s, "ctype": ctype[:40],
                                    "status": response.status,
                                    "len": response.headers.get("content-length"),
                                    "range": response.headers.get("content-range", "")[:40]}
                            diag["media_candidates"].append(cand)
                            # 尝试捕获完整视频字节（200 全量响应）
                            if response.status == 200 and ("video" in ctype or ".mp4" in low):
                                try:
                                    body = response.body()
                                    if body and len(body) > 1000:
                                        part = STAGING / f"{PILOT_NOTE}.mp4.part"
                                        part.parent.mkdir(parents=True, exist_ok=True)
                                        part.write_bytes(body)
                                        cand["captured_to"] = str(part)
                                        cand["captured_bytes"] = len(body)
                                except Exception as e:
                                    diag["errors"].append(f"capture {s[:60]}: {str(e)[:80]}")
                        # 身份证据：detail payload 含 note_id
                        if "json" in ctype and PILOT_NOTE in u:
                            diag["identity_evidence"].append({"page": tag, "safe": s})
                    except Exception:
                        pass

                def on_dl(download):
                    diag["downloads"].append({"page": tag, "suggested": download.suggested_filename})

                page.on("response", on_resp)
                page.on("download", on_dl)
                diag["pages_seen"].append(tag)

            # 现有 3 tab
            for role in ("CREATOR", "SPOTLIGHT", "FRONTEND"):
                try:
                    p = runtime.ensure_tabs().get(role)
                    if p:
                        watch_page(p, role)
                except Exception:
                    pass
            # 新开页（用户点击详情可能开新 tab/popup）
            def on_new(page):
                try:
                    watch_page(page, "NEW")
                except Exception:
                    pass
            context.on("page", on_new)

            # 导航到笔记管理（已发布 tab）
            try:
                tab.goto("https://creator.xiaohongshu.com/new/note-manager", timeout=60000)
                time.sleep(8)
                tab.reload(timeout=60000)
                time.sleep(6)
            except Exception as e:
                diag["errors"].append(f"nav: {str(e)[:80]}")

            # ========== 自动定位目标笔记（搜索 + 高亮，用户只需点击） ==========
            import unicodedata as _ud
            _core = "".join(c for c in _ud.normalize("NFKC", (title or "")) if c.isalnum() or "\u4e00" <= c <= "\u9fff")
            kw = _core[:24] or PILOT_NOTE
            located = False
            for _try in range(3):
                located = tab.evaluate(
                    """(d) => {
                      const i = document.querySelector('input[placeholder*="搜索已发布"], input[placeholder*="搜索"]');
                      if (!i) return false;
                      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                      setter.call(i, d.kw);
                      i.dispatchEvent(new Event('input', {bubbles:true}));
                      i.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true, cancelable:true}));
                      i.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', bubbles:true, cancelable:true}));
                      return true;
                    }""", {"kw": kw, "nid": PILOT_NOTE})
                time.sleep(5)
                # 找目标卡片（标题核心词匹配）并高亮滚动
                hl = tab.evaluate(
                    """(core) => {
                      const els = Array.from(document.querySelectorAll('[class*=note-card], [class*=card], [class*=item]'));
                      const coreNorm = (t) => (t||'').replace(/[\\s\\u0000-\\u001f]/g, '');
                      for (const e of els) {
                        const t = (e.textContent||'');
                        if (t.length > 8 && t.length < 300 && coreNorm(t).includes(core.slice(0,8))) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 200) {
                            e.scrollIntoView({block: 'center'});
                            e.style.outline = '4px solid #ff4d4f';
                            e.style.outlineOffset = '2px';
                            return t.slice(0, 60);
                          }
                        }
                      }
                      return null;
                    }""", _core)
                if hl:
                    safe_print("LOCATED_CARD = " + str(hl[:50]).encode("gbk", errors="replace").decode("gbk"))
                    located = True
                    break
                time.sleep(2)
            if not located:
                diag["errors"].append("auto-locate failed; user may find manually")

            # ========== 提示用户 ==========
            safe_print("=" * 70)
            safe_print("【V0.6.1 人工辅助恢复 Pilot1】")
            safe_print("TreeCut 已在笔记管理中自动搜索并【红色高亮】目标卡片（带 00:21 时长角标）。")
            safe_print(f"  note_id : {PILOT_NOTE}")
            safe_print("请点击被红色框高亮的那张卡片/其预览入口：")
            safe_print("TreeCut 已挂载观察器，正在等待你点击……（最多 45 分钟）")
            safe_print("=" * 70)

            # ========== 等待用户打开（轮询身份/媒体） ==========
            deadline = time.time() + 2700  # 45 分钟
            outcome = {"identity": None, "media": None}
            while time.time() < deadline:
                # 身份：任何页面 URL 或内容含 note_id
                for p in context.pages:
                    try:
                        u = p.url or ""
                        if PILOT_NOTE in u:
                            outcome["identity"] = {"source": "url", "page_url": u[:160]}
                    except Exception:
                        pass
                if diag["identity_evidence"]:
                    outcome["identity"] = {"source": "detail_payload",
                                           "evidence": diag["identity_evidence"][-1]}
                # 媒体捕获完成？
                if any(c.get("captured_to") for c in diag["media_candidates"]):
                    outcome["media"] = "captured"
                    break
                if diag["media_candidates"] and diag.get("_media_stable", False):
                    break
                time.sleep(2)
            return outcome

        outcome = runtime._in_browser(run, timeout=1000)
        print("OUTCOME =", json.dumps(outcome, ensure_ascii=True))

        # ========== 身份门 + 验证 ==========
        identity_ok = bool(outcome.get("identity"))
        part_file = None
        for c in diag["media_candidates"]:
            if c.get("captured_to") and Path(c["captured_to"]).exists():
                part_file = Path(c["captured_to"])
                break

        result = {"pilot": "V06_ASSISTED_PILOT1", "note_id": PILOT_NOTE,
                  "creator_duration": creator_duration,
                  "identity_gate": {"expected": PILOT_NOTE, "actual_source": outcome.get("identity"),
                                    "pass": identity_ok},
                  "media_candidates_count": len(diag["media_candidates"]),
                  "media_captured": bool(part_file)}
        if not identity_ok or not part_file:
            result["status"] = "V06_ASSISTED_PILOT1_NEEDS_REPAIR"
            result["reason"] = "identity not confirmed or no media bytes captured"
        else:
            result["status"] = validate_and_promote(part_file, creator_duration, result)
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
        print("PILOT1_DONE")


def validate_and_promote(part: Path, creator_duration, result) -> str:
    """ffprobe + full decode + sha256 + duration crosscheck → promote Z / quarantine。"""
    tech = {"file": str(part), "size": part.stat().st_size}
    try:
        out = subprocess.run([FFPROBE, "-v", "error", "-show_format", "-show_streams",
                              "-of", "json", str(part)], capture_output=True, text=True, timeout=120)
        probe = json.loads(out.stdout or "{}")
        fmt = probe.get("format", {})
        streams = probe.get("streams", [])
        vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
        astream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        duration = float(fmt.get("duration") or 0)
        tech.update({
            "ffprobe_ok": bool(vstream and duration > 0),
            "duration": duration, "video_codec": (vstream or {}).get("codec_name"),
            "width": (vstream or {}).get("width"), "height": (vstream or {}).get("height"),
            "fps": eval_rational((vstream or {}).get("avg_frame_rate") or (vstream or {}).get("r_frame_rate")),
            "audio_codec": (astream or {}).get("codec_name") if astream else None,
        })
    except Exception as e:
        tech["ffprobe_error"] = str(e)[:120]
        result["status"] = "V06_ASSISTED_PILOT1_NEEDS_REPAIR"
        return result["status"]

    # full decode
    try:
        dec = subprocess.run([FFMPEG, "-v", "error", "-i", str(part), "-f", "null", "-"],
                             capture_output=True, text=True, timeout=600)
        tech["full_decode_ok"] = dec.returncode == 0
        if dec.stderr:
            tech["decode_stderr_tail"] = dec.stderr.strip()[-200:]
    except Exception as e:
        tech["decode_error"] = str(e)[:120]
        tech["full_decode_ok"] = False

    # sha256
    h = hashlib.sha256()
    with open(part, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    sha = h.hexdigest()
    tech["sha256"] = sha

    # duration crosscheck
    dur = tech.get("duration") or 0
    tol = max(5.0, creator_duration * 0.15) if creator_duration else 5.0
    match = abs(dur - creator_duration) <= tol
    tech["duration_crosscheck"] = {"creator": creator_duration, "ffprobe": round(dur, 2),
                                   "tolerance": round(tol, 2), "pass": match}

    ok = (tech.get("ffprobe_ok") and tech.get("full_decode_ok") and sha
          and tech["duration_crosscheck"]["pass"])
    (OUT / "B007_V061_MEDIA_TECH_METADATA.json").write_text(
        json.dumps(tech, ensure_ascii=False, indent=2), encoding="utf-8")

    if ok:
        Z_MEDIA.mkdir(parents=True, exist_ok=True)
        final = Z_MEDIA / f"{PILOT_NOTE}__{sha[:12]}.mp4"
        part.replace(final)  # 原子 promote
        tech["final_path"] = str(final)
        # registry
        conn = sqlite3.connect(DB, timeout=30)
        conn.execute("DELETE FROM b007_published_media_recovery_v1 WHERE note_id=?", (PILOT_NOTE,))
        conn.execute(
            "INSERT INTO b007_published_media_recovery_v1(note_id,sample_id,expected_note_id,actual_note_id,"
            "recovery_status,source_type,container,byte_size,sha256,duration,width,height,fps,video_codec,"
            "audio_codec,creator_duration,duration_match_status,final_path,recovered_at,validation_version,"
            "block_reason,attempts,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (PILOT_NOTE, "PILOT1", PILOT_NOTE, PILOT_NOTE, "RECOVERED_EXACT", "USER_ASSISTED_CREATOR_DETAIL",
             "mp4", tech["size"], sha, tech.get("duration"), tech.get("width"), tech.get("height"),
             tech.get("fps"), tech.get("video_codec"), tech.get("audio_codec"), creator_duration,
             "MATCH_WITHIN_TOLERANCE" if match else "MISMATCH", str(final),
             time.strftime("%Y-%m-%d %H:%M:%S"), "V0.6.1-PILOT1", None, 1, time.time()))
        conn.commit()
        conn.close()
        result["tech"] = tech
        return "V06_ASSISTED_PILOT1_PASS"
    # quarantine
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    q = QUARANTINE / f"{PILOT_NOTE}.part"
    part.replace(q)
    tech["quarantined_to"] = str(q)
    result["tech"] = tech
    return "V06_ASSISTED_PILOT1_NEEDS_REPAIR"


def eval_rational(v):
    try:
        a, b = str(v).split("/")
        return round(float(a) / float(b), 3)
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
