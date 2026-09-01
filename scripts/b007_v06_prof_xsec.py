# -*- coding: utf-8 -*-
"""V0.6 — 带 xsec 的 B007 主页：导航 → 笔记渲染 → 点击笔记卡（xsec）→ 视频媒体。"""
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
                for _ in range(6):
                    try:
                        return ftab.evaluate(expr, arg)
                    except Exception:
                        time.sleep(2.5)
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

            # 搜索 → 拿带 xsec 的主页链接
            nav("https://www.xiaohongshu.com/search_result?keyword=" + quote("KUBON坤宝高端岛台工厂"))
            prof_href = ev(
                """() => {
                  for (const a of document.querySelectorAll('a[href*="/user/profile/"]')) {
                    const href = a.getAttribute('href') || '';
                    if (href.includes('xsec_token')) return href;
                  }
                  return null;
                }""")
            print("PROF_HREF =", (prof_href or "")[:150])
            if not prof_href:
                return
            full = "https://www.xiaohongshu.com" + prof_href if prof_href.startswith("/") else prof_href
            media = []

            def on_media(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    s = _safe(u)
                    if "video" in ctype or ".mp4" in u.lower() or ".m3u8" in u.lower() or "sns-video" in s:
                        media.append({"safe": s, "ctype": ctype[:40], "len": response.headers.get("content-length")})
                except Exception:
                    pass

            ftab.on("response", on_media)
            nav(full)
            notes = ev("""() => {
                const out = [];
                for (const a of document.querySelectorAll('a[href*="/explore/"], a[href*="/discovery/item/"]')) {
                  const href = a.getAttribute('href') || '';
                  const m = href.match(/([0-9a-fA-F]{24})/);
                  if (m && href.includes('xsec')) out.push({id: m[1], href: href.slice(0,140)});
                }
                const seen=new Set(); const uniq=[];
                for (const x of out) { if (!seen.has(x.id)) { seen.add(x.id); uniq.push(x); } }
                return {count: uniq.length, sample: uniq.slice(0,8)};
              }""")
            try:
                print("PROF_URL =", ftab.url[:160])
            except Exception:
                pass
            print("PROFILE_NOTES =", json.dumps(notes, ensure_ascii=True))
            # 找样本 note 卡片（滚动）
            found = None
            for _ in range(20):
                found = ev("""(nid) => {
                      for (const a of document.querySelectorAll('a[href*="/explore/"], a[href*="/discovery/item/"]')) {
                        const href = a.getAttribute('href') || '';
                        if (href.includes(nid)) { a.click(); return href.slice(0,150); }
                      }
                      return null;
                    }""", SAMPLE)
                if found:
                    break
                ev("() => window.scrollBy(0, 1500)")
                time.sleep(2)
            print("SAMPLE_FOUND =", found)
            time.sleep(10)
            try:
                u = ftab.url or ""
            except Exception:
                u = ""
            m = re.search(r"/(?:explore|discovery/item)/([0-9a-fA-F]{24})", u)
            print("URL_NOTE =", m.group(1) if m else None)
            has_video = ev("() => { const v=document.querySelector('video'); if (v) { v.muted=true; v.play().catch(()=>{}); return true; } return false; }")
            print("HAS_VIDEO =", has_video)
            time.sleep(12)
            ftab.remove_listener("response", on_media)
            print("MEDIA =", json.dumps(media[:8], ensure_ascii=True))
        runtime._in_browser(probe, timeout=600)
        return 0
    finally:
        runtime.close()
        print("PROF_XSEC_DONE")


if __name__ == "__main__":
    sys.exit(main())
