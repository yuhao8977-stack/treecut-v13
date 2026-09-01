# -*- coding: utf-8 -*-
"""V0.6 — 主页路径完整单样本尝试：profile-xsec → 滚动找卡 → 点击 → note 页媒体全 dump。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

SAMPLE = "69f9a0ac000000003701d937"


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

        def probe():
            ftab = runtime.ensure_tabs().get("FRONTEND")

            def ev(expr, arg=None):
                for _ in range(10):
                    try:
                        return ftab.evaluate(expr, arg)
                    except Exception:
                        time.sleep(2)
                return None

            def nav(url):
                try:
                    ftab.goto(url, timeout=60000)
                except Exception:
                    pass
                try:
                    ftab.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass
                time.sleep(6)

            media = []
            all_media_eps = []

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    s = _safe(u)
                    if "video" in ctype or ".mp4" in u.lower() or ".m3u8" in u.lower() or "sns-video" in s:
                        media.append({"safe": s, "ctype": ctype[:40], "len": response.headers.get("content-length")})
                        if s not in all_media_eps:
                            all_media_eps.append(s)
                except Exception:
                    pass

            ftab.on("response", on_response)
            nav("https://www.xiaohongshu.com/search_result?keyword=" + quote("KUBON坤宝高端岛台工厂"))
            prof_href = ev("""() => {
                for (const a of document.querySelectorAll('a[href*="/user/profile/"]')) {
                  const href = a.getAttribute('href') || '';
                  if (href.includes('xsec_token')) return href;
                }
                return null;
              }""")
            if not prof_href:
                print("NO_PROF_XSEC")
                return
            nav("https://www.xiaohongshu.com" + prof_href)
            print("PROF_LOADED")
            # 激进滚动找样本卡
            found = None
            for i in range(40):
                found = ev("""(nid) => {
                  for (const a of document.querySelectorAll('a[href*="/explore/"], a[href*="/discovery/item/"]')) {
                    const href = a.getAttribute('href') || '';
                    const r = a.getBoundingClientRect();
                    if (href.includes(nid) && r.width > 50) { a.click(); return href.slice(0,160); }
                  }
                  window.scrollBy(0, 1200);
                  return null;
                }""", SAMPLE)
                if found:
                    print("FOUND_AT_SCROLL =", i)
                    break
                time.sleep(1.2)
            print("FOUND =", found)
            # 等 note 页
            note_ok = False
            for _ in range(15):
                try:
                    u = ftab.url or ""
                except Exception:
                    u = ""
                m = re.search(r"/(?:explore|discovery/item)/([0-9a-fA-F]{24})", u)
                if m and m.group(1) == SAMPLE:
                    note_ok = True
                    break
                time.sleep(2)
            print("NOTE_OK =", note_ok)
            time.sleep(5)
            # 全页 dump：video、媒体链接、播放控件
            page = ev("""() => {
                const v = document.querySelector('video');
                const vids = Array.from(document.querySelectorAll('video')).map(x => ({src: (x.currentSrc||'').slice(0,120), dur: x.duration}));
                const srcs = [];
                for (const el of document.querySelectorAll('source, video')) { if (el.src) srcs.push(el.src.slice(0,120)); }
                return {has_video: !!v, vids: vids, srcs: srcs.slice(0,5),
                        text_len: (document.body.innerText||'').length};
              }""")
            print("PAGE =", json.dumps(page, ensure_ascii=True))
            # 尝试播放
            ev("""() => {
                const v = document.querySelector('video');
                if (v) { v.muted = true; v.play().catch(()=>{}); }
                const els = Array.from(document.querySelectorAll('[class*=play], [class*=video], [class*=player]'));
                for (const e of els) { const r = e.getBoundingClientRect(); if (r.width > 40 && r.height > 40) { e.click(); break; } }
              }""")
            time.sleep(15)
            ftab.remove_listener("response", on_response)
            print("MEDIA =", json.dumps(media[:10], ensure_ascii=True))
        runtime._in_browser(probe, timeout=700)
        return 0
    finally:
        runtime.close()
        print("PROFILE_FULL_DONE")


if __name__ == "__main__":
    sys.exit(main())
