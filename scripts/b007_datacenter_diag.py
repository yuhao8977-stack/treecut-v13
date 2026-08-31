# -*- coding: utf-8 -*-
"""诊断：数据中心 导出按钮定位（DOM 校准，§20）。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

URLS = [
    "https://creator.xiaohongshu.com/data/overview",
    "https://creator.xiaohongshu.com/data/note",
    "https://creator.xiaohongshu.com/data/content",
]


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
            for u in URLS:
                try:
                    tab.goto(u, timeout=60000)
                    time.sleep(5)
                except Exception as e:
                    print(f"{u}: NAV_FAIL {str(e)[:80]}")
                    continue
                try:
                    info = tab.evaluate(
                        """() => {
                          const out = [];
                          const els = Array.from(document.querySelectorAll('button,a,span,div,[class*=export],[class*=download],[class*=btn]'));
                          for (const e of els) {
                            const t = (e.textContent||'').trim();
                            if (/导出|下载|export|download/i.test(t) && t.length <= 20) {
                              const r = e.getBoundingClientRect();
                              out.push({text: t, cls: (e.className||'').toString().slice(0,70),
                                        visible: r.width>0 && r.height>0});
                            }
                          }
                          const uniq = [];
                          const seen = new Set();
                          for (const x of out) { const k = x.text+'|'+x.cls; if (!seen.has(k)) { seen.add(k); uniq.push(x); } }
                          return {url: location.href.slice(0,80), title: (document.title||'').slice(0,50),
                                  hits: uniq.slice(0,25), text_len: (document.body.innerText||'').length};
                        }""")
                    print("== ", json.dumps(info, ensure_ascii=True)[:1500])
                except Exception as e:
                    print(f"{u}: EVAL_FAIL {str(e)[:80]}")
        runtime._in_browser(diag, timeout=400)
        return 0
    finally:
        runtime.close()
        print("DC_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
