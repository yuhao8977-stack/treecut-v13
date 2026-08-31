# -*- coding: utf-8 -*-
"""诊断2：平台首页侧边栏菜单 → 找数据中心/导出入口。"""
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
            tab.goto("https://creator.xiaohongshu.com/", timeout=60000)
            time.sleep(6)
            # 侧边栏菜单
            try:
                menu = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('a,span,div,li'));
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (t.length >= 2 && t.length <= 8 && /笔记|数据|创作|内容|互动|营销|管理|分析|首页|导出/.test(t)) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 0 && r.height > 0) {
                            const a = e.closest('a');
                            out.push({text: t, href: a ? (a.getAttribute('href')||'') : '', cls: (e.className||'').toString().slice(0,40)});
                          }
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out) { const k=x.text+'|'+x.href; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return {url: location.href.slice(0,100), title:(document.title||'').slice(0,50),
                              menu: uniq.slice(0,40), text_len:(document.body.innerText||'').length};
                    }""")
                print("MENU =", json.dumps(menu, ensure_ascii=True)[:2500])
            except Exception as e:
                print("menu fail", str(e)[:100])
        runtime._in_browser(diag, timeout=300)
        return 0
    finally:
        runtime.close()
        print("HOME_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
