# -*- coding: utf-8 -*-
"""V0.3.1 — 探索「数据」板块：子菜单、报表页面、日期控件、笔记维度。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

HOME = "https://ad.xiaohongshu.com/"

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
            # 点导航「数据」
            clicked = tab.evaluate(
                """() => {
                  const els = Array.from(document.querySelectorAll('div,span,li,a'));
                  const t = els.find(e => (e.textContent||'').trim() === '数据' && e.children.length <= 1);
                  if (t) { t.click(); return true; }
                  return false;
                }""")
            print("CLICK_DATA_NAV =", clicked)
            time.sleep(3)
            # dump 子菜单
            try:
                sub = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('a,li,div,span'));
                      const re = /报表|报告|笔记|内容|账户|人群|关键词|搜索|直播|商品|数据|概览/;
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (re.test(t) && t.length >= 2 && t.length <= 12) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 0 && r.height > 0) {
                            const a = e.closest('a');
                            out.push({text: t, href: a ? (a.getAttribute('href')||'') : '',
                                      cls: (e.className||'').toString().slice(0,50)});
                          }
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out){ const k=x.text+'|'+x.href; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return uniq.slice(0,35);
                    }""")
                print("DATA_SUBMENU =", json.dumps(sub, ensure_ascii=True))
            except Exception as e:
                print("sub fail", str(e)[:80])
            print("URL =", tab.url[:120])
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("DATA_NAV_DONE")


if __name__ == "__main__":
    sys.exit(main())
