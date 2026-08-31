# -*- coding: utf-8 -*-
"""V0.3 — 单元页分页控件精确 dump。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

UNIT_PAGE = "https://ad.xiaohongshu.com/aurora/ad/manage/unit"

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
            tab.goto(UNIT_PAGE, timeout=60000)
            time.sleep(8)
            tab.reload(timeout=60000)
            time.sleep(8)
            # 全页所有文本 ∈ {数字, 上一页, 下一页, >, <} 的可点击元素
            try:
                info = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('li,a,button,span,div'));
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (/^(<|>|«|»|‹|›|上一页|下一页|\\d{1,2})$/.test(t)) {
                          const r = e.getBoundingClientRect();
                          const cs = getComputedStyle(e);
                          if (r.width > 0 && r.height > 0 && cs.visibility !== 'hidden') {
                            out.push({t: t, tag: e.tagName, cls: (e.className||'').toString().slice(0,60),
                                      role: e.getAttribute('role')||''});
                          }
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out){ const k=x.t+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return uniq.slice(0,40);
                    }""")
                print("PAG_UI =", json.dumps(info, ensure_ascii=True))
            except Exception as e:
                print("fail", str(e)[:80])
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("PAG_UI_DONE")


if __name__ == "__main__":
    sys.exit(main())
