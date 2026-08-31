# -*- coding: utf-8 -*-
"""V0.3.1 — dump Spotlight 顶部导航（概览/推广/创意/数据/资产/工具/财务）真实结构。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

HOME = "https://ad.xiaohongshu.com/aurora/ad/manage/campaign"

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
            tab = runtime.ensure_tabs().get("SPOTLIGHT")
            tab.goto(HOME, timeout=60000)
            time.sleep(8)
            # dump 所有顶层可见导航项
            nav = tab.evaluate(
                """() => {
                  const out = [];
                  const els = Array.from(document.querySelectorAll('a,li,div,span'));
                  for (const e of els) {
                    const t = (e.textContent||'').trim();
                    if (t && t.length <= 6 && /概览|推广|创意|数据|资产|工具|财务/.test(t)) {
                      const r = e.getBoundingClientRect();
                      if (r.width > 0 && r.height > 0) {
                        const a = e.closest('a');
                        out.push({text: t, href: a ? (a.getAttribute('href')||'') : '',
                                  tag: e.tagName, cls: (e.className||'').toString().slice(0,70)});
                      }
                    }
                  }
                  const uniq=[]; const seen=new Set();
                  for (const x of out){ const k=x.text+'|'+x.href+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                  return uniq.slice(0,30);
                }""")
            print("NAV =", json.dumps(nav, ensure_ascii=True))
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("NAV_DUMP_DONE")


if __name__ == "__main__":
    sys.exit(main())
