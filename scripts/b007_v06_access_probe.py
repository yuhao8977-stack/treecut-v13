# -*- coding: utf-8 -*-
"""V0.6 — 媒体可达性探测：不同年代样本 explore URL + 个人主页导航路径。"""
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

TEST_NOTES = [
    ("C-2026", "69f9a0ac000000003701d937"),
    ("A-2023", "6544d761000000001f038f12"),
    ("F-2022", "63a6a53f000000001f00d5e2"),
]
NOTE_ID_RE = re.compile(r"([0-9a-fA-F]{24})")
PROFILE = "https://www.xiaohongshu.com/user/profile/63083262719"


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
            tab = runtime.ensure_tabs().get("FRONTEND")
            for label, nid in TEST_NOTES:
                try:
                    tab.goto(f"https://www.xiaohongshu.com/explore/{nid}", timeout=45000)
                    time.sleep(6)
                    u = tab.url or ""
                    m = NOTE_ID_RE.search(u)
                    ok = "404" not in u and m and m.group(1) == nid
                    print(f"{label} {nid}: url={u[:120]} | direct_ok={ok}")
                except Exception as e:
                    print(f"{label}: NAV_FAIL {str(e)[:80]}")
            # 个人主页路径
            print(f"\nPROFILE {PROFILE}")
            try:
                tab.goto(PROFILE, timeout=60000)
                time.sleep(8)
                print("profile url:", tab.url[:120])
                # SSR 状态中找 xsec note 链接
                r = tab.evaluate(
                    """() => {
                      const out = [];
                      const links = document.querySelectorAll('a[href*="/explore/"], a[href*="/discovery/item/"]');
                      for (const a of links) {
                        const href = a.getAttribute('href') || '';
                        const m = href.match(/([0-9a-fA-F]{24})/);
                        if (m) out.push({id: m[1], href: href.slice(0, 120)});
                      }
                      const seen = new Set(); const uniq = [];
                      for (const x of out) { if (!seen.has(x.id)) { seen.add(x.id); uniq.push(x); } }
                      return uniq.slice(0, 8);
                    }""")
                print("PROFILE_NOTE_LINKS =", json.dumps(r, ensure_ascii=True))
                # 点第一个 note → 观察 URL 格式
                try:
                    clicked = tab.evaluate(
                        """() => {
                          const links = document.querySelectorAll('a[href*="/explore/"], a[href*="/discovery/item/"]');
                          if (links[0]) { links[0].click(); return true; }
                          return false;
                        }""")
                    print("CLICK_FIRST_NOTE =", clicked)
                    time.sleep(7)
                    print("AFTER_CLICK url:", tab.url[:160])
                except Exception as e:
                    print("click fail", str(e)[:80])
            except Exception as e:
                print("profile fail", str(e)[:100])
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("ACCESS_PROBE_DONE")


if __name__ == "__main__":
    sys.exit(main())
