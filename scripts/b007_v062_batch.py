# -*- coding: utf-8 -*-
"""V0.6.2 — SAMPLE20 BATCH EXACT MEDIA RECOVERY (AUTO CREATOR NAVIGATION + HUMAN FALLBACK).

V0.6.2 导航事实（探针实证）：note-manager 搜索 API 在自动化下不生效（恒 items=0，DOM 实为默认
「已发布」列表按时间倒序滚动分页）。因此 AUTO 导航改为：
  已发布列表（时间倒序）→ 容器滚动逐页加载 → 按 发布时间(精确)+时长徽标+标题 匹配目标卡片
  → Playwright 真实点击 Creator 卡片 → 平台打开合法 Frontend Detail(page-owned xsec)
  → 观察媒体 → 会话内完整获取 → 验证 → 提升 Z。
剩余笔记按 publish_time DESC 排序串行处理，一次向前滚动可顺序收割多条。
HUMAN 兜底：滚动到底仍未命中 → 【需要你点击】窗口等用户正常打开。
纪律：identity hard gate(note_id 唯一)、title 仅 NAVIGATION_HINT、媒体 URL 仅内存、
统一 duration 容差、全量 ffmpeg decode、SHA256、exact-duplicate 引用、E staging + Z(shutil.move)、
checkpoint/resume、C-drive guard、Z gate、SERIAL 单 worker。
退出码: 0=batch 全部 terminal; 43=GLOBAL_STOP(captcha/session); 2=profile locked。
用法: python b007_v062_batch.py [--human-window 600] [--limit N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
STAGING = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\staging\B007")
QUARANTINE = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\quarantine")
Z_MEDIA = Path(r"Z:\TreeCut_Media\B007\published_media")
NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"
MANIFEST = OUT / "B007_SAMPLE20_V1.json"
CHECKPOINT = OUT / "B007_V062_CHECKPOINT_V1.json"
LIVE_STATUS = OUT / "B007_V062_LIVE_STATUS.json"
PILOT1_ID = "69f9a0ac000000003701d937"
FFPROBE = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
FFMPEG = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"

CAPTURE_DEADLINE = 180.0
SCROLL_WAIT = 2.8
MAX_SCROLLS = 400
MAX_DOWNLOADS = 3
CAPTCHA_MARKERS = ["拖动滑块", "安全验证", "验证码", "人机验证", "完成拼图"]


def bring_browser_forward() -> None:
    """把 Edge 浏览器窗口置前（用户在其它窗口时也能看到高亮卡）。stdout 丢弃避免管道捕获限制。"""
    try:
        import subprocess
        ps = ("Add-Type @'using System;using System.Runtime.InteropServices;"
              "public class W { [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr h); }'@;"
              "Get-Process msedge | Where-Object { $_.MainWindowTitle -ne '' } |"
              " ForEach-Object { [W]::SetForegroundWindow($_.MainWindowHandle) }")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    except Exception:
        pass


def safe_print(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("gbk", errors="replace").decode("gbk"))
        except Exception:
            print("(console print failed)")


def _safe(url: str) -> str:
    try:
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


def normalize_title(t: str) -> str:
    t = re.sub(r"[\U00010000-\U0010FFFF]", "", t or "")
    t = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", t)
    return t


def eval_r(v):
    try:
        a, b = str(v).split("/")
        return round(float(a) / float(b), 3)
    except Exception:
        return None


def dt_key(dt: str | None):
    """'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD' → 可比较字符串；None → 最早。"""
    if not dt:
        return "0000-00-00 00:00"
    if len(dt) == 10:
        return dt + " 00:00"
    return dt


# ---------------------------------------------------------------- checkpoint
def load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        try:
            return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"rule": "V0.6.2-SAMPLE20-BATCH-EXACT-MEDIA-RECOVERY",
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "notes": {}}


def save_checkpoint(cp: dict) -> None:
    cp["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    CHECKPOINT.write_text(json.dumps(cp, ensure_ascii=False, indent=2), encoding="utf-8")


def write_live(status: dict) -> None:
    LIVE_STATUS.write_text(json.dumps(status, ensure_ascii=True, indent=2), encoding="utf-8")


TERMINAL = {"ALREADY_RECOVERED_VALID", "RECOVERED_EXACT", "NOTE_UNAVAILABLE",
            "MEDIA_NOT_OBSERVED", "MEDIA_VALIDATION_FAILED", "QUARANTINED",
            "FAILED_NEEDS_HUMAN", "NOTE_IDENTITY_MISMATCH"}


# ---------------------------------------------------------------- db helpers
def db_upsert(sample, tech: dict | None, status: str, source_type: str, block_reason: str,
              attempts: int, nav_mode: str, actual_note_id: str | None, canonical: dict | None = None) -> None:
    note_id = sample["note_id"]
    final_path = None
    sha = None
    if canonical:
        final_path = canonical.get("final_path")
        sha = canonical.get("sha256")
    elif tech:
        final_path = tech.get("final_path")
        sha = tech.get("sha256")
    for _ in range(6):
        try:
            conn = sqlite3.connect(DB, timeout=30)
            conn.execute("DELETE FROM b007_published_media_recovery_v1 WHERE note_id=?", (note_id,))
            conn.execute(
                "INSERT INTO b007_published_media_recovery_v1(note_id,sample_id,expected_note_id,actual_note_id,"
                "recovery_status,source_type,container,byte_size,sha256,duration,width,height,fps,video_codec,"
                "audio_codec,creator_duration,duration_match_status,final_path,recovered_at,validation_version,"
                "block_reason,attempts,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (note_id, sample["sample_id"], note_id, actual_note_id or note_id, status, source_type,
                 (tech or {}).get("container") or ("mp4" if tech else None),
                 (tech or {}).get("size"), sha, (tech or {}).get("duration"),
                 (tech or {}).get("width"), (tech or {}).get("height"), (tech or {}).get("fps"),
                 (tech or {}).get("video_codec"), (tech or {}).get("audio_codec"),
                 sample.get("duration"),
                 (tech or {}).get("duration_match_status"), final_path,
                 time.strftime("%Y-%m-%d %H:%M:%S"),
                 f"V0.6.2-{nav_mode}", block_reason or None, attempts, time.time()))
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                time.sleep(1.0)
                continue
            safe_print(f"  [db] {e}")
            return
    safe_print("  [db] write failed after retries")


# ---------------------------------------------------------------- media fetch
def fetch_full(ctx, url: str, timeout=120000):
    try:
        resp = ctx.request.get(url, timeout=timeout)
    except Exception:
        return None
    if not resp.ok:
        return None
    body = resp.body()
    if resp.status == 206:
        cr = resp.headers.get("content-range", "") or ""
        m = re.search(r"/(\d+)\s*$", cr)
        total = int(m.group(1)) if m else len(body)
        if len(body) < total:
            try:
                r2 = ctx.request.get(url, headers={"Range": "bytes=0-"}, timeout=timeout)
                if r2.ok and len(r2.body()) > len(body):
                    return r2
            except Exception:
                pass
    return resp


# ---------------------------------------------------------------- validation
def validate_media(part: Path, creator_dur: float) -> dict:
    tech = {"file": str(part), "size": part.stat().st_size}
    try:
        out = subprocess.run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(part)],
                             capture_output=True, timeout=120)
        probe = json.loads(out.stdout.decode("utf-8", errors="replace"))
        fmt = probe.get("format", {})
        streams = probe.get("streams", [])
        vs = next((s for s in streams if s.get("codec_type") == "video"), None)
        au = next((s for s in streams if s.get("codec_type") == "audio"), None)
        dur = float(fmt.get("duration") or (vs or {}).get("duration") or 0)
        tech.update({"ffprobe_ok": bool(vs and dur > 0), "duration": dur,
                     "video_codec": (vs or {}).get("codec_name"),
                     "width": (vs or {}).get("width"), "height": (vs or {}).get("height"),
                     "fps": eval_r((vs or {}).get("avg_frame_rate")),
                     "audio_codec": (au or {}).get("codec_name") if au else None})
    except Exception as e:
        tech["ffprobe_error"] = str(e)[:200]
        tech["ffprobe_ok"] = False
    try:
        dec = subprocess.run([FFMPEG, "-v", "error", "-i", str(part), "-f", "null", "-"],
                             capture_output=True, timeout=600)
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
    tol = max(5.0, creator_dur * 0.15)
    dur = tech.get("duration") or 0
    match = tech.get("ffprobe_ok") and abs(dur - creator_dur) <= tol
    tech["duration_crosscheck"] = {"creator": creator_dur, "ffprobe": round(dur, 2),
                                   "tolerance": round(tol, 2), "pass": bool(match)}
    tech["duration_match_status"] = "MATCH_WITHIN_TOLERANCE" if match else "MISMATCH"
    tech["ok"] = bool(tech.get("ffprobe_ok") and tech.get("full_decode_ok") and sha and match)
    return tech


def find_existing_sha(sha: str, note_id: str):
    try:
        conn = sqlite3.connect(DB, timeout=30)
        rows = conn.execute(
            "SELECT note_id, final_path FROM b007_published_media_recovery_v1 "
            "WHERE sha256=? AND note_id<>?", (sha, note_id)).fetchall()
        conn.close()
        for nid, fp in rows:
            if fp and Path(fp).exists():
                return {"note_id": nid, "final_path": fp, "sha256": sha}
    except Exception:
        pass
    for f in Z_MEDIA.glob(f"*__{sha[:12]}*"):
        return {"note_id": None, "final_path": str(f), "sha256": sha}
    return None


def promote(sample, tech: dict, nav_mode: str, attempts: int) -> str:
    note_id = sample["note_id"]
    part = Path(tech["file"])
    sha = tech["sha256"]
    Z_MEDIA.mkdir(parents=True, exist_ok=True)
    dup = find_existing_sha(sha, note_id)
    if dup:
        tech["final_path"] = dup["final_path"]
        tech["blob_mode"] = "REFERENCE"
        tech["canonical_note"] = dup["note_id"]
        db_upsert(sample, tech, "RECOVERED_EXACT", f"PAGE_OWNED_MEDIA_OBSERVATION/{nav_mode}",
                  None, attempts, nav_mode, note_id, canonical=dup)
        part.unlink(missing_ok=True)
        return "RECOVERED_EXACT"
    final = Z_MEDIA / f"{note_id}__{sha[:12]}.mp4"
    shutil.move(str(part), str(final))
    tech["final_path"] = str(final)
    tech["blob_mode"] = "NEW_BLOB"
    db_upsert(sample, tech, "RECOVERED_EXACT", f"PAGE_OWNED_MEDIA_OBSERVATION/{nav_mode}",
              None, attempts, nav_mode, note_id)
    return "RECOVERED_EXACT"


def quarantine_part(sample, tech: dict, nav_mode: str, attempts: int) -> None:
    part = Path(tech["file"])
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    q = QUARANTINE / f"{sample['note_id']}.{int(time.time())}.part"
    if part.exists():
        shutil.move(str(part), str(q))
        tech["quarantined_to"] = str(q)
    db_upsert(sample, tech, "MEDIA_VALIDATION_FAILED", f"PAGE_OWNED_MEDIA_OBSERVATION/{nav_mode}",
              f"ffprobe_ok={tech.get('ffprobe_ok')} full_decode_ok={tech.get('full_decode_ok')} "
              f"duration_match={tech.get('duration_match_status')}", attempts, nav_mode, sample["note_id"])


# ---------------------------------------------------------------- browser flow
def build_observers(runtime, diag: dict, note_id: str, full_urls: list, sweep: dict):
    """点击之前挂载 observers（spec §17）；galaxy 列表 API 被动观察 → sweep（跨调用共享，定位真源）。"""
    ctx = runtime._context

    def watch(page, tag):
        def on_resp(response):
            try:
                u = response.url or ""
                ctype = (response.headers.get("content-type") or "").lower()
                s = _safe(u)
                low = u.lower()
                if "json" in ctype and note_id in u:
                    diag.setdefault("identity_evidence", []).append({"page": tag, "safe": s})
                if "creator/note/user/posted" in u:
                    try:
                        body = response.body()[:4000000]
                        data = json.loads(body.decode("utf-8", errors="replace"))
                        items = ((data.get("data") or {}).get("items")
                                 or (data.get("data") or {}).get("notes") or [])
                        for it in items:
                            nid = str(it.get("id") or it.get("noteId") or it.get("note_id") or "")
                            if not nid:
                                continue
                            vi = str(it.get("video_info") or "")
                            m = re.search(r"duration['\"]?\s*[:=]\s*(\d+)", vi)
                            dur = int(m.group(1)) if m else None
                            rec = {"id": nid,
                                   "time": str(it.get("time") or "")[:16],
                                   "duration": dur,
                                   "title": str(it.get("display_title") or it.get("title") or "")}
                            key = rec["id"]
                            if key not in sweep["seen"]:
                                sweep["seen"].add(key)
                                sweep["items"].append(rec)
                    except Exception:
                        pass
                is_video = "video" in ctype or ".mp4" in low or ".webm" in low
                if is_video:
                    cand = {"page": tag, "safe": s, "ctype": ctype[:40], "status": response.status,
                            "len": response.headers.get("content-length"),
                            "range": (response.headers.get("content-range") or "")[:40]}
                    diag.setdefault("media_candidates", []).append(cand)
                    if u not in full_urls and len(full_urls) < 8:
                        full_urls.append(u)
            except Exception:
                pass
        try:
            page.on("response", on_resp)
            page.on("download", lambda dl: diag.setdefault("downloads", []).append(dl.suggested_filename))
            diag.setdefault("pages_seen", []).append(tag)
        except Exception:
            pass

    for role in ("CREATOR", "SPOTLIGHT", "FRONTEND"):
        try:
            p = runtime.ensure_tabs().get(role)
            if p:
                watch(p, role)
        except Exception:
            pass
    ctx.on("page", lambda p: watch(p, "NEW"))


def check_captcha(tab) -> bool:
    try:
        txt = tab.evaluate("() => (document.body.innerText || '').slice(0, 6000)")
        for m in CAPTCHA_MARKERS:
            if m in (txt or ""):
                return True
        if tab.locator("iframe[src*=captcha], [class*=captcha-dialog], [class*=captcha-modal]").count() > 0:
            return True
    except Exception:
        pass
    return False


def find_detail_page(ctx, note_id: str):
    for p in ctx.pages:
        try:
            if f"/explore/{note_id}" in p.url or f"explore/{note_id}" in p.url:
                return p
        except Exception:
            pass
    return None


def find_wrong_detail(ctx, note_id: str):
    for p in ctx.pages:
        try:
            m = re.search(r"/explore/([0-9a-f]{24})", p.url)
            if m and m.group(1) != note_id:
                return m.group(1)
        except Exception:
            pass
    return None


def note_deleted_text(p) -> bool:
    try:
        t = p.evaluate("() => (document.body.innerText || '').slice(0, 4000)")
        return any(k in (t or "") for k in ["笔记不存在", "内容已删除", "该内容已被删除", "内容已被删除", "笔记已删除"])
    except Exception:
        return False


def resolve_by_signals(tab, exp_time: str, exp_dur, exp_title: str) -> int:
    """在 DOM 全量卡片中按 发布时间 + 时长徽标 + 标题 解析目标卡片索引。
    用完整 innerText（长卡片时间可能在 300 字符之外）。"""
    try:
        return int(tab.evaluate(
            """(sig) => {
              const expTime = sig.time, expDur = sig.dur, expTitle = sig.title;
              const els = Array.from(document.querySelectorAll('[class*=note-card]'));
              const norm = s => (s||'').replace(/[^\\u4e00-\\u9fffA-Za-z0-9]/g, '');
              for (let i=0;i<els.length;i++){
                const r = els[i].getBoundingClientRect();
                if (r.width<=200 || r.height<=50) continue;
                const txt = (els[i].innerText||'').replace(/\\n+/g,'|');
                const timeOk = expTime && txt.indexOf(expTime.slice(0,16)) >= 0;
                if (!timeOk) continue;
                const m = txt.match(/(\\d{1,2}):(\\d{2})/);
                const durOk = expDur ? (m ? Math.abs((+m[1])*60 + (+m[2]) - expDur) <= Math.max(3, expDur*0.2) : false) : true;
                const normTxt = norm(txt);
                const titleOk = expTitle ? (normTxt.indexOf(expTitle) >= 0 || (expTitle.length>8 && normTxt.indexOf(expTitle.slice(0,8)) >= 0)) : true;
                if (timeOk && (durOk || titleOk)) return i;
              }
              return -1;
            }""", {"time": exp_time or "", "dur": exp_dur, "title": exp_title or ""}))
    except Exception:
        return -1


def scroll_list(tab) -> None:
    """滚动所有可滚动容器 + 窗口到底（V0.2 实证：触发页面自身 posted?page=N 分页）。"""
    try:
        tab.evaluate(
            """() => {
              const els = Array.from(document.querySelectorAll('*'));
              const sc = els.filter(e => e.scrollHeight > e.clientHeight + 100
                && getComputedStyle(e).overflowY !== 'visible');
              for (const e of sc) e.scrollTop = e.scrollHeight;
              window.scrollTo(0, document.body.scrollHeight);
            }""")
    except Exception:
        pass


def capture_phase(ctx, note_id: str, full_urls: list, diag: dict, deadline: float,
                  detail_page=None) -> list:
    parts = []
    downloaded = set()
    pages_for_play = [detail_page] if detail_page else ctx.pages
    while time.time() < deadline and len(parts) < MAX_DOWNLOADS:
        for p in pages_for_play:
            try:
                p.evaluate(
                    """() => {
                      const v = document.querySelector('video');
                      if (v) {
                        v.muted = true;
                        if (v.currentTime === 0 || v.paused) { v.play().catch(()=>{}); }
                        if (v.currentSrc && location.href.indexOf('explore') >= 0) {
                          window.__TC_SRC__ = v.currentSrc;
                        }
                      }
                      const els = Array.from(document.querySelectorAll('[class*=play],[class*=video],[class*=player]'));
                      for (const e of els) { const r = e.getBoundingClientRect(); if (r.width>40 && r.height>40) { try{e.click();}catch(_){} break; } }
                    }""")
                src = p.evaluate("() => window.__TC_SRC__ || null")
                if src and src not in full_urls:
                    full_urls.append(src)
            except Exception:
                pass
        if full_urls:
            for url in list(full_urls):
                if url in downloaded or len(parts) >= MAX_DOWNLOADS:
                    continue
                resp = fetch_full(ctx, url)
                if resp and resp.ok:
                    body = resp.body()
                    if body and len(body) > 1000:
                        part = STAGING / f"{note_id}.{len(parts)}.part"
                        part.parent.mkdir(parents=True, exist_ok=True)
                        part.write_bytes(body)
                        diag.setdefault("media_candidates", []).append(
                            {"page": "SESSION_DOWNLOAD", "safe": _safe(url),
                             "ctype": resp.headers.get("content-type", "")[:40],
                             "status": resp.status, "captured_to": str(part),
                             "captured_bytes": len(body)})
                        parts.append(str(part))
                        downloaded.add(url)
                        safe_print(f"  [capture] downloaded {len(body)} bytes -> {part.name}")
                else:
                    downloaded.add(url)
        time.sleep(2.0)
    return parts


def highlight_card(tab, found_idx: int) -> None:
    """目标卡红色高亮边框（仅 UI 提示，不改平台行为）。"""
    try:
        tab.evaluate(
            """(idx) => {
              const el = document.querySelectorAll('[class*=note-card]')[idx];
              if (!el) return;
              el.scrollIntoView({block:'center', inline:'center'});
              el.style.outline = '3px solid #ff2f2f';
              el.style.outlineOffset = '2px';
              el.setAttribute('data-tc-target', '1');
            }""", found_idx)
    except Exception:
        pass


def process_position(runtime, sample, diag: dict, goto_fresh: bool, sweep: dict):
    """定位阶段（HUMAN_CLICK 模式）：已发布列表滚动 → 目标卡可见 + 红色高亮。不做点击。"""
    note_id = sample["note_id"]
    ctx = runtime._context
    tab = runtime.ensure_tabs().get("CREATOR")
    full_urls = []
    build_observers(runtime, diag, note_id, full_urls, sweep)
    if goto_fresh:
        tab.goto(NOTE_MANAGER, timeout=60000)
        time.sleep(9)
        try:
            tab.evaluate(
                "() => { const els = Array.from(document.querySelectorAll('div,span,li,a,button'));"
                " const t = els.find(e => (e.textContent||'').trim() === '已发布' && e.children.length <= 2);"
                " if (t) { t.click(); return true; } return false; }")
            time.sleep(3)
        except Exception:
            pass
    if check_captcha(tab):
        return {"global": "CAPTCHA"}
    # ---- 定位：优先已加载(sweep) → 否则继续滚动直到目标出现或列表耗尽
    target_rec = next((it for it in sweep["items"] if it["id"] == note_id), None)
    rounds = 0
    stall = 0
    while target_rec is None and rounds < MAX_SCROLLS:
        before = len(sweep["items"])
        scroll_list(tab)
        time.sleep(SCROLL_WAIT)
        rounds += 1
        after = len(sweep["items"])
        target_rec = next((it for it in sweep["items"] if it["id"] == note_id), None)
        stall = stall + 1 if after == before else 0
        if rounds % 20 == 0:
            safe_print(f"  [scroll] round={rounds} loaded={after} stall={stall}")
        if stall >= 6:                                   # 连续滚动无新页 → 列表耗尽
            break
    if target_rec is None:
        diag["scroll_result"] = {"status": "NOT_FOUND", "rounds": rounds,
                                 "loaded": len(sweep["items"])}
        return {"global": None, "ok": False, "positioned": False}
    # ---- API 已命中，但 DOM 卡片可能尚未渲染：轮询等待（≤20s，附滚动微调）
    exp_time = (target_rec.get("time") or sample.get("publish_time") or "")[:16]
    exp_dur = target_rec.get("duration") or sample.get("duration")
    exp_title = normalize_title(target_rec.get("title") or sample.get("title"))
    found_idx = -1
    for _ in range(8):
        found_idx = resolve_by_signals(tab, exp_time, exp_dur, exp_title)
        if found_idx >= 0:
            break
        scroll_list(tab)
        time.sleep(2.5)
    if found_idx < 0 and exp_title:
        # 兜底：仅标题命中（norm 标题前 10 字符唯一匹配）
        found_idx = tab.evaluate(
            """(t10) => {
              const els = Array.from(document.querySelectorAll('[class*=note-card]'));
              const norm = s => (s||'').replace(/[^\\u4e00-\\u9fffA-Za-z0-9]/g, '');
              for (let i=0;i<els.length;i++){
                const r = els[i].getBoundingClientRect();
                if (r.width<=200 || r.height<=50) continue;
                const nt = norm((els[i].innerText||''));
                if (nt.indexOf(t10) >= 0) return i;
              }
              return -1;
            }""", exp_title[:10])
    diag["scroll_result"] = {"status": "FOUND" if found_idx >= 0 else "RESOLVE_FAILED",
                             "rounds": rounds, "loaded": len(sweep["items"]),
                             "api_time": exp_time, "api_duration": exp_dur, "index": found_idx}
    if found_idx < 0:
        diag.setdefault("errors", []).append("resolve_by_signals failed (card not in DOM after wait)")
        return {"global": None, "ok": False, "positioned": False}
    # ---- 目标卡可见 + 红色高亮（等用户点击）
    highlight_card(tab, found_idx)
    time.sleep(1.5)
    return {"global": None, "ok": True, "positioned": True, "index": found_idx}


def process_human(runtime, sample, diag: dict, sweep: dict):
    """HUMAN HANDOFF 验收模式：等待用户真实点击（无界等待，不烧计时/不标 FAILED/不推进）。

    周期性把 Edge 窗口置前 + 刷新 live status；用户点击打开目标详情后：
    actual_note_id gate → media observation → capture → 返回 parts。"""
    note_id = sample["note_id"]
    ctx = runtime._context
    tab = runtime.ensure_tabs().get("CREATOR")
    full_urls = []
    build_observers(runtime, diag, note_id, full_urls, sweep)
    try:
        if "/new/" not in tab.url:
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(6)
    except Exception:
        pass
    if check_captcha(tab):
        return {"global": "CAPTCHA"}
    # ---- 无界等待用户真实点击（无超时）
    last_remind = 0.0
    while True:
        detail = find_detail_page(ctx, note_id)
        if detail:
            break
        if check_captcha(tab):
            return {"global": "CAPTCHA"}
        now = time.time()
        if now - last_remind > 45:                      # 每 45s 置前浏览器 + 刷新提示
            last_remind = now
            bring_browser_forward()
            try:
                write_live({"overall": "WAITING_FOR_HUMAN_CLICK",
                            "current": {"sample_id": sample["sample_id"], "note_id": note_id,
                                        "title": sample.get("title"),
                                        "stratum": sample.get("primary_stratum"),
                                        "phase": "WAITING_FOR_HUMAN_CLICK — 请点击红色高亮卡片",
                                        "status": "WAITING_FOR_HUMAN_CLICK"},
                            "needs_human": {"note_id": note_id, "title": sample.get("title"),
                                            "publish_time": sample.get("publish_time"),
                                            "duration": sample.get("duration"),
                                            "positioned": True,
                                            "hint": "点击红色高亮的目标卡片（不要下载/复制URL）"}})
            except Exception:
                pass
        time.sleep(2.0)
    if note_deleted_text(detail):
        return {"global": None, "opened": True, "note_deleted": True}
    diag["identity"] = {"status": "MATCH", "evidence": "detail_url"}
    parts = capture_phase(ctx, note_id, full_urls, diag, time.time() + 150, detail_page=detail)
    return {"global": None, "opened": True, "parts": parts}


def close_task_pages(runtime, note_id: str) -> None:
    ctx = runtime._context
    managed = set()
    for role in ("CREATOR", "SPOTLIGHT", "FRONTEND"):
        try:
            p = runtime.ensure_tabs().get(role)
            if p:
                managed.add(id(p))
        except Exception:
            pass
    for p in list(ctx.pages):
        try:
            if id(p) in managed:
                continue
            if f"/explore/{note_id}" in p.url:
                p.close()
        except Exception:
            pass


def reconcile_final(runtime) -> None:
    ctx = runtime._context
    managed = set()
    for role in ("CREATOR", "SPOTLIGHT", "FRONTEND"):
        try:
            p = runtime.ensure_tabs().get(role)
            if p:
                managed.add(id(p))
        except Exception:
            pass
    for p in list(ctx.pages):
        try:
            if id(p) in managed:
                continue
            if "/explore/" in p.url:
                p.close()
        except Exception:
            pass


# ---------------------------------------------------------------- pilot verify
def verify_pilot(cp: dict) -> None:
    if cp.get("pilot_validated"):
        return
    nid = PILOT1_ID
    entry = {"sample_id": "SC-69f9a0ac", "status": "ALREADY_RECOVERED_VALID", "attempts": 0,
             "nav_mode": "PILOT1", "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        conn = sqlite3.connect(DB, timeout=30)
        row = conn.execute("SELECT sha256, final_path FROM b007_published_media_recovery_v1 "
                           "WHERE note_id=? AND recovery_status='RECOVERED_EXACT'", (nid,)).fetchone()
        conn.close()
        if row:
            sha, fp = row
            f = Path(fp)
            if f.exists():
                h = hashlib.sha256()
                with open(f, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                sha_ok = h.hexdigest() == sha
                out = subprocess.run([FFPROBE, "-v", "error", "-show_format", "-of", "json", str(f)],
                                     capture_output=True, timeout=120)
                probe = json.loads(out.stdout.decode("utf-8", errors="replace"))
                dur = float(probe.get("format", {}).get("duration") or 0)
                ffprobe_ok = dur > 0
                entry.update({"sha256": sha, "final_path": fp, "sha256_match": sha_ok,
                              "ffprobe_ok": ffprobe_ok, "duration": round(dur, 2)})
                entry["status"] = "ALREADY_RECOVERED_VALID" if (sha_ok and ffprobe_ok) else "NEEDS_REPAIR_CHECK"
            else:
                entry["status"] = "PILOT1_FILE_MISSING"
    except Exception as e:
        entry["status"] = f"PILOT1_CHECK_ERROR: {str(e)[:120]}"
    cp["pilot_validated"] = entry
    cp.setdefault("notes", {})[nid] = entry
    save_checkpoint(cp)
    safe_print(f"PILOT1 = {entry['status']}")


# ---------------------------------------------------------------- main
def main() -> int:
    global CHECKPOINT, LIVE_STATUS
    ap = argparse.ArgumentParser()
    ap.add_argument("--human-window", type=float, default=600.0)
    ap.add_argument("--limit", type=int, default=0, help="最多处理 N 条(0=全部)；用于单条验证")
    ap.add_argument("--manifest-file", default=str(MANIFEST), help="样本清单 JSON（含 samples 列表）")
    ap.add_argument("--checkpoint", default=str(CHECKPOINT), help="checkpoint 文件路径")
    ap.add_argument("--live", default=str(LIVE_STATUS), help="live status 文件路径")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    CHECKPOINT = Path(args.checkpoint)
    LIVE_STATUS = Path(args.live)
    manifest = json.loads(Path(args.manifest_file).read_text(encoding="utf-8"))
    samples = manifest["samples"]
    assert len(samples) >= 1 and all(s["note_id"] for s in samples)

    cp = load_checkpoint()
    if not cp.get("started_at") or args.checkpoint != str(CHECKPOINT):
        # 使用独立 checkpoint（如 Recent12）时避免混入 Sample20 状态
        if args.checkpoint != str(CHECKPOINT):
            cp = {"rule": "V0.6.2-BATCH-MEDIA-RECOVERY",
                  "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                  "notes": {}}
        cp["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        cp["c_free_before_gb"] = round(shutil.disk_usage("C:\\").free / 2**30, 1)
    notes = cp.setdefault("notes", {})
    if args.manifest_file == str(MANIFEST):
        verify_pilot(cp)

    Z_MEDIA.mkdir(parents=True, exist_ok=True)
    if not Z_MEDIA.exists():
        safe_print("Z_GATE_FAILED: Z unavailable -> stop media recovery")
        return 43

    config = load_config()
    config.workspace_id = "B007"
    config.validate()
    runtime = BrowserRuntime(config)
    try:
        runtime.workspace.acquire_lock()
    except RuntimeError as error:
        safe_print(f"PROFILE_LOCKED: {error}")
        return 2
    try:
        runtime.start_browser(headless=False)
        runtime.reconcile_tabs()
        # 剩余笔记按发布时间倒序（与已发布列表滚动方向一致，一次前向收割多条）
        remaining = [s for s in samples
                     if notes.get(s["note_id"], {}).get("status") not in TERMINAL]
        remaining.sort(key=lambda s: dt_key(s.get("publish_time")), reverse=True)
        consecutive_fail = 0
        processed = 0
        goto_fresh = True
        sweep = {"items": [], "seen": set()}           # galaxy 列表 API 被动观察（跨调用共享）
        for sample in remaining:
            nid = sample["note_id"]
            if args.limit and processed >= args.limit:
                safe_print(f"[limit] reached {args.limit} processed notes this run")
                break
            processed += 1
            title = sample.get("title", "")
            stratum = sample.get("primary_stratum", "")
            safe_print(f"\n=== {sample['sample_id']} {nid} | {stratum} | "
                       f"pub={sample.get('publish_time')} dur={sample.get('duration')}s ===")
            safe_print(f"    title: {title}")
            done = len([n for n in notes.values() if n.get("status") in TERMINAL])
            write_live({"overall": f"{done} / 20", "current": {
                "sample_id": sample["sample_id"], "note_id": nid, "title": title,
                "stratum": stratum, "phase": "正在Creator列表定位", "status": "processing"},
                "needs_human": None})
            attempts = notes.get(nid, {}).get("attempts", 0) + 1
            nav_mode = "HUMAN"          # V0.6.2 生产模式：定位AUTO + 点击HUMAN + 媒体恢复AUTO
            diag = {}
            # ---- 阶段1: 定位（已发布列表滚动 sweep → 目标卡红色高亮；不做点击）
            try:
                r = runtime._in_browser(lambda: process_position(runtime, sample, diag, goto_fresh, sweep),
                                        timeout=600)
            except Exception as e:
                r = {"global": None, "ok": False, "error": str(e)[:200]}
            goto_fresh = False                      # 之后续滚，不从顶部重来
            if r.get("global") == "CAPTCHA":
                safe_print("GLOBAL_CAPTCHA -> batch STOP")
                notes[nid] = {**notes.get(nid, {}), "status": "NAVIGATION_NEEDS_HUMAN",
                              "attempts": attempts,
                              "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                save_checkpoint(cp)
                return 43
            positioned = bool(r.get("positioned"))
            # ---- 阶段2: 提示用户点击高亮卡片 → 等待点击 + 自动捕获/验证/提升
            bring_browser_forward()                 # 浏览器窗口置前，方便用户看到高亮卡
            write_live({"overall": f"{done} / 20", "current": {
                "sample_id": sample["sample_id"], "note_id": nid, "title": title,
                "stratum": stratum, "phase": "【请点击当前目标笔记】(红色高亮卡片)",
                "status": "AWAIT_HUMAN_CLICK"},
                "needs_human": {"note_id": nid, "title": title,
                                "publish_time": sample.get("publish_time"),
                                "duration": sample.get("duration"),
                                "positioned": positioned,
                                "hint": "点击红色高亮的目标卡片（不要下载/复制URL）"}})
            safe_print(">>> 【请点击当前目标笔记】可见浏览器中红色高亮卡片 = 目标；点击后自动恢复媒体")
            safe_print(f">>> title={title} publish={sample.get('publish_time')} "
                       f"dur={sample.get('duration')}s note_id={nid} positioned={positioned}")
            diag2 = {}
            try:
                hr = runtime._in_browser(lambda: process_human(runtime, sample, diag2, sweep),
                                         timeout=43200)      # 无界等待（12h 上限仅为 executor 保护）
            except Exception as e:
                hr = {"global": None, "opened": False, "error": str(e)[:200]}
            if hr.get("global") == "CAPTCHA":
                safe_print("GLOBAL_CAPTCHA -> batch STOP")
                save_checkpoint(cp)
                return 43
            if not hr.get("opened"):
                # 仅当非预期（异常/全局问题）才走到这里；真实点击未发生时应永远停留在等待
                safe_print(f"UNEXPECTED_HANDOFF_EXIT: {hr.get('error', 'no detail')}")
                notes[nid] = {**notes.get(nid, {}), "status": "NAVIGATION_NEEDS_HUMAN",
                              "attempts": attempts, "nav_mode": nav_mode, "diag": diag2,
                              "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                save_checkpoint(cp)
                return 43
            if hr.get("opened") and hr.get("note_deleted"):
                status = "NOTE_UNAVAILABLE"
                safe_print(f"NOTE_UNAVAILABLE (detail shows deleted/not-exist) -> {status}")
                db_upsert(sample, None, status, f"PAGE_OWNED_MEDIA_OBSERVATION/{nav_mode}",
                          "detail page indicates note deleted/unavailable", attempts, nav_mode, nid)
                notes[nid] = {**notes.get(nid, {}), "status": status, "attempts": attempts,
                              "nav_mode": nav_mode, "diag": diag2,
                              "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                save_checkpoint(cp)
                continue
            if hr.get("opened"):
                parts = hr.get("parts") or []
                if not parts:
                    status = "MEDIA_NOT_OBSERVED"
                    safe_print(f"HUMAN opened but no media -> {status}")
                    db_upsert(sample, None, status, f"PAGE_OWNED_MEDIA_OBSERVATION/{nav_mode}",
                              "detail opened by user but no video bytes observed", attempts, nav_mode, nid)
                    notes[nid] = {**notes.get(nid, {}), "status": status, "attempts": attempts,
                                  "nav_mode": nav_mode, "diag": diag2,
                                  "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                    save_checkpoint(cp)
                    consecutive_fail += 1
                    continue
                tech = None
                for pth in parts:
                    t = validate_media(Path(pth), sample.get("duration") or 0)
                    if t.get("ok"):
                        tech = t
                        break
                if tech:
                    status = promote(sample, tech, nav_mode, attempts)
                    safe_print(f"STATUS={status} sha256={tech['sha256'][:16]}... "
                               f"dur={round(tech.get('duration') or 0,2)}s final={tech.get('final_path')}")
                    safe_print("HUMAN_HANDOFF_ACCEPTANCE = PASS")
                    notes[nid] = {"sample_id": sample["sample_id"], "status": status, "attempts": attempts,
                                  "nav_mode": nav_mode, "sha256": tech["sha256"],
                                  "final_path": tech.get("final_path"), "tech": tech,
                                  "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                    consecutive_fail = 0
                else:
                    first_tech = validate_media(Path(parts[0]), sample.get("duration") or 0)
                    quarantine_part(sample, first_tech, nav_mode, attempts)
                    safe_print(f"STATUS=MEDIA_VALIDATION_FAILED -> quarantined (dur={first_tech.get('duration')})")
                    for extra in parts[1:]:
                        Path(extra).unlink(missing_ok=True)
                    notes[nid] = {**notes.get(nid, {}), "status": "MEDIA_VALIDATION_FAILED",
                                  "attempts": attempts, "nav_mode": nav_mode, "tech": first_tech,
                                  "diag": diag2, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                    consecutive_fail += 1
                save_checkpoint(cp)
                write_live({"overall": f"{done + 1} / 20", "current": {
                    "sample_id": sample["sample_id"], "note_id": nid, "title": title,
                    "stratum": stratum, "phase": "已保存", "status": status}, "needs_human": None})
                continue
        # ---- 收尾
        reconcile_final(runtime)
        done = len([n for n in notes.values() if n.get("status") in TERMINAL])
        safe_print(f"\nBATCH_END done={done}/20")
        if done < 20:
            pending = [nid for nid, n in notes.items() if n.get("status") not in TERMINAL]
            safe_print(f"NOT_TERMINAL: {pending}")
        return 0
    finally:
        try:
            runtime.close()
        except Exception:
            pass
        safe_print("BATCH_DONE")


if __name__ == "__main__":
    sys.exit(main())
