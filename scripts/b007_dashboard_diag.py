# -*- coding: utf-8 -*-
"""诊断3：数据看板子菜单 → 笔记数据 → 导出按钮。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime


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

        def diag():
            tab = runtime.ensure_tabs().get("CREATOR")
            tab.goto("https://creator.xiaohongshu.com/new/home", timeout=60000)
            time.sleep(6)
            # 点 数据看板 子菜单
            try:
                r = tab.evaluate(
                    """() => {
                      const els = Array.from(document.querySelectorAll('div,span,li,a'));
                      const t = els.find(e => (e.textContent||'').trim() === '数据看板');
                      if (t) { t.click(); return true; }
                      return false;
                    }""")
                print("CLICK_DASHBOARD =", r)
                time.sleep(3)
            except Exception as e:
                print("click fail", str(e)[:100])
            # dump 子菜单项 + 当前页
            try:
                info = tab.evaluate(
                    """() => {
                      const items = [];
                      const els = Array.from(document.querySelectorAll('a,li,div,span'));
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (t.length >= 2 && t.length <= 10 && /笔记数据|直播数据|商品|互动|粉丝|内容数据|导出|下载/.test(t)) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 0 && r.height > 0) {
                            const a = e.closest('a');
                            items.push({text: t, href: a ? (a.getAttribute('href')||'') : ''});
                          }
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of items) { const k=x.text+'|'+x.href; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return {url: location.href.slice(0,120), title:(document.title||'').slice(0,60),
                              items: uniq.slice(0,30)};
                    }""")
                print("DASH =", json.dumps(info, ensure_ascii=True)[:2000])
            except Exception as e:
                print("dump fail", str(e)[:100])
        runtime._in_browser(diag, timeout=300)
        return 0
    finally:
        runtime.close()
        print("DASH_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
