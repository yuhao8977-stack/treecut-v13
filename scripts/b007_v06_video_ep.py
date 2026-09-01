# -*- coding: utf-8 -*-
"""V0.6 — galaxy/creator/user/video 端点内容 + 搜索滚动匹配。"""
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
            import io
            import unicodedata as _ud
            manifest = json.load(io.open(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_SAMPLE20_V1.json", encoding="utf-8"))
            title = next(s["title"] for s in manifest["samples"] if s["note_id"] == SAMPLE) or ""
            core = "".join(c for c in _ud.normalize("NFKC", title) if c.isalnum() or "\u4e00" <= c <= "\u9fff")
            ctab = runtime.ensure_tabs().get("CREATOR")
            video_bodies = []

            def on_resp(response):
                try:
                    u = response.url or ""
                    if "user/video" in u:
                        b = response.json()
                        video_bodies.append(b)
                except Exception:
                    pass

            ctab.on("response", on_resp)
            ctab.goto("https://creator.xiaohongshu.com/new/note-manager", timeout=60000)
            time.sleep(10)
            ctab.remove_listener("response", on_resp)
            print("USER_VIDEO_BODIES =", len(video_bodies))
            if video_bodies:
                d = video_bodies[0].get("data")
                print("  shape:", json.dumps(d, ensure_ascii=False)[:600])

            # 搜索路径（滚动 + note_id 匹配）
            ftab = runtime.ensure_tabs().get("FRONTEND")
            kw = quote(core[:24])
            ftab.goto(f"https://www.xiaohongshu.com/search_result?keyword={kw}", timeout=60000)
            time.sleep(8)
            found = None
            for _ in range(8):
                found = ftab.evaluate(
                    """(nid) => {
                      for (const a of document.querySelectorAll('a[href*="/explore/"]')) {
                        const href = a.getAttribute('href') || '';
                        if (href.includes(nid)) { a.click(); return href.slice(0,160); }
                      }
                      return null;
                    }""", SAMPLE)
                if found:
                    break
                try:
                    ftab.evaluate("() => window.scrollBy(0, 1200)")
                    time.sleep(2)
                except Exception:
                    break
            print("FOUND =", found)
            time.sleep(10)
            m = re.search(r"/(?:explore|discovery/item)/([0-9a-fA-F]{24})", ftab.url or "")
            print("URL_NOTE =", m.group(1) if m else None, "| url:", ftab.url[:150])
        runtime._in_browser(probe, timeout=500)
        return 0
    finally:
        runtime.close()
        print("VIDEO_EP_DONE")


if __name__ == "__main__":
    sys.exit(main())
