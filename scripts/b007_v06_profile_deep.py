# -*- coding: utf-8 -*-
"""V0.6 — 个人主页 DOM 深挖：会话、卡片、链接格式、滚动。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

PROFILE = "https://www.xiaohongshu.com/user/profile/63083262719"


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
            tab.goto(PROFILE, timeout=60000)
            time.sleep(10)
            info = tab.evaluate(
                """() => {
                  const out = {url: location.href.slice(0,120), title: (document.title||'').slice(0,60),
                               text_len: (document.body.innerText||'').length,
                               head: (document.body.innerText||'').slice(0,200)};
                  const cards = document.querySelectorAll('section.note-item, [class*=note-item], [class*=feeds] a, a[href]');
                  const links = [];
                  for (const a of document.querySelectorAll('a[href]')) {
                    const href = a.getAttribute('href') || '';
                    if (/item|explore|note/.test(href) && !/user\/profile/.test(href)) links.push(href.slice(0,140));
                  }
                  out.link_count = links.length;
                  out.links = links.slice(0, 10);
                  out.note_item_count = document.querySelectorAll('[class*=note-item], [class*=noteItem]').length;
                  return out;
                }""")
            print("PROFILE_DOM =", json.dumps(info, ensure_ascii=True))
            # 滚动触发卡片
            try:
                for _ in range(5):
                    tab.evaluate("() => window.scrollBy(0, 1500)")
                    time.sleep(1.5)
                links = tab.evaluate(
                    """() => {
                      const out = [];
                      for (const a of document.querySelectorAll('a[href]')) {
                        const href = a.getAttribute('href') || '';
                        const m = href.match(/([0-9a-fA-F]{24})/);
                        if (m && /item|explore|note/.test(href)) out.push({id: m[1], href: href.slice(0,150)});
                      }
                      const seen=new Set(); const uniq=[];
                      for (const x of out) { if (!seen.has(x.id)) { seen.add(x.id); uniq.push(x); } }
                      return {count: uniq.length, sample: uniq.slice(0,8)};
                    }""")
                print("AFTER_SCROLL =", json.dumps(links, ensure_ascii=True))
            except Exception as e:
                print("scroll fail", str(e)[:80])
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("PROFILE_DEEP_DONE")


if __name__ == "__main__":
    sys.exit(main())
