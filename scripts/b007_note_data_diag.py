# -*- coding: utf-8 -*-
"""诊断4：数据看板 → 笔记数据子页面 → 导出按钮。"""
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
            # 打开 数据看板 子菜单
            tab.evaluate(
                "() => { const els = Array.from(document.querySelectorAll('div,span,li,a'));"
                " const t = els.find(e => (e.textContent||'').trim() === '数据看板');"
                " if (t) { t.click(); return true; } return false; }")
            time.sleep(2)
            # 点子菜单 笔记数据
            clicked = tab.evaluate(
                "() => { const els = Array.from(document.querySelectorAll('div,span,li,a'));"
                " const t = els.find(e => { const x=(e.textContent||'').trim();"
                "   return (x === '笔记数据' || x === '笔记数据总览') && e.children.length <= 2; });"
                " if (t) { t.click(); return true; } return false; }")
            print("CLICK_NOTE_DATA =", clicked)
            time.sleep(6)
            # 当前 URL + 导出按钮扫描（全页面文本）
            try:
                info = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('button,a,span,div,[class*=export],[class*=download]'));
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (/导出|下载|export|download/i.test(t) && t.length <= 20) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 0 && r.height > 0) {
                            const a = e.closest('a');
                            out.push({text: t, href: a ? (a.getAttribute('href')||'') : '',
                                      cls: (e.className||'').toString().slice(0,60)});
                          }
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out) { const k=x.text+'|'+x.href+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return {url: location.href.slice(0,150), title:(document.title||'').slice(0,60),
                              hits: uniq.slice(0,20), text_len:(document.body.innerText||'').length};
                    }""")
                print("NOTE_DATA =", json.dumps(info, ensure_ascii=True)[:1800])
            except Exception as e:
                print("dump fail", str(e)[:100])
        runtime._in_browser(diag, timeout=300)
        return 0
    finally:
        runtime.close()
        print("ND_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
