# -*- coding: utf-8 -*-
"""V0.6 — 单样本恢复核心验证：profile-xsec → 找卡点击 → 等导航 → 触发播放 → 捕获媒体 URL。"""
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
                for _ in range(8):
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

            def on_media(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    s = _safe(u)
                    if "video" in ctype or ".mp4" in u.lower() or ".m3u8" in u.lower() or "sns-video" in s or "snssdk" in s:
                        media.append({"safe": s, "ctype": ctype[:40], "len": response.headers.get("content-length"),
                                      "range": response.headers.get("content-range", "")[:40]})
                except Exception:
                    pass

            ftab.on("response", on_media)
            # 1) 搜索拿 profile xsec
            nav("https://www.xiaohongshu.com/search_result?keyword=" + quote("KUBON坤宝高端岛台工厂"))
            prof_href = ev("""() => {
                for (const a of document.querySelectorAll('a[href*="/user/profile/"]')) {
                  const href = a.getAttribute('href') || '';
                  if (href.includes('xsec_token')) return href;
                }
                return null;
              }""")
            print("PROF_HREF_OK =", bool(prof_href))
            full = "https://www.xiaohongshu.com" + prof_href if prof_href and prof_href.startswith("/") else prof_href
            # 2) 主页（xsec）
            nav(full)
            time.sleep(5)
            # 3) 滚动找样本卡并点击（不点未滚动到的）
            found = None
            for _ in range(30):
                found = ev("""(nid) => {
                  const links = Array.from(document.querySelectorAll('a[href*="/explore/"], a[href*="/discovery/item/"]'));
                  for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    const r = a.getBoundingClientRect();
                    if (href.includes(nid) && r.width > 50) { a.click(); return href.slice(0,160); }
                  }
                  window.scrollBy(0, 1400);
                  return null;
                }""", SAMPLE)
                if found:
                    break
                time.sleep(1.5)
            print("FOUND =", found)
            # 4) 等待导航到 note 页
            note_url = None
            for _ in range(15):
                try:
                    u = ftab.url or ""
                except Exception:
                    u = ""
                m = re.search(r"/(?:explore|discovery/item)/([0-9a-fA-F]{24})", u)
                if m and m.group(1) == SAMPLE:
                    note_url = u
                    break
                time.sleep(2)
            print("NOTE_URL =", (note_url or "")[:160])
            # 5) 触发播放
            time.sleep(4)
            ev("() => { const v=document.querySelector('video'); if (v) { v.muted=true; v.play().catch(()=>{}); return 'video'; } return 'novideo'; }")
            time.sleep(14)
            has_video = ev("() => !!document.querySelector('video')")
            print("HAS_VIDEO_ELEM =", has_video)
            ftab.remove_listener("response", on_media)
            print("MEDIA =", json.dumps(media[:10], ensure_ascii=True))
        runtime._in_browser(probe, timeout=600)
        return 0
    finally:
        runtime.close()
        print("SINGLE_RECOVERY_DONE")


if __name__ == "__main__":
    sys.exit(main())
