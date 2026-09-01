# -*- coding: utf-8 -*-
"""V0.6 — 前台整体可达性：首页 feed + 随机公开笔记 explore。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime


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
            # 1) 首页 feed
            try:
                ftab.goto("https://www.xiaohongshu.com/", timeout=60000)
                time.sleep(10)
                info = ftab.evaluate(
                    "() => { const links = Array.from(document.querySelectorAll('a[href]'));"
                    " const n = links.filter(a => /explore\\/[0-9a-fA-F]{24}/.test(a.getAttribute('href')||'')).length;"
                    " return {url: location.href.slice(0,80), text_len: (document.body.innerText||'').length,"
                    " feed_note_links: n}; }")
                print("HOME =", json.dumps(info, ensure_ascii=True))
            except Exception as e:
                print("home fail", str(e)[:80])
            # 2) 从 feed 拿一个随机 note 链接（含 xsec）并打开
            try:
                r = ftab.evaluate(
                    """() => {
                      const links = Array.from(document.querySelectorAll('a[href*="/explore/"]'));
                      if (!links.length) return null;
                      const href = links[0].getAttribute('href') || '';
                      return href.slice(0, 200);
                    }""")
                print("FEED_NOTE_HREF =", r)
                if r and r.startswith("/explore/"):
                    ftab.goto("https://www.xiaohongshu.com" + r, timeout=60000)
                    time.sleep(8)
                    print("RANDOM_NOTE_URL =", ftab.url[:160])
                    m = re.search(r"explore/([0-9a-fA-F]{24})", ftab.url or "")
                    print("RANDOM_NOTE_ID =", m.group(1) if m else None)
            except Exception as e:
                print("feed note fail", str(e)[:80])
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("FE_ACCESS_DONE")


if __name__ == "__main__":
    sys.exit(main())
