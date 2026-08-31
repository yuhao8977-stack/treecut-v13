# -*- coding: utf-8 -*-
"""诊断：note-manager 分页机制 + 直接 fetch page=N 是否可行。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"


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
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(4)
            # 点已发布
            try:
                tab.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('div,span,li,a,button'));"
                    " const t = els.find(e => (e.textContent||'').trim() === '已发布' && e.children.length <= 2);"
                    " if (t) { t.click(); return true; } return false; }")
                time.sleep(2)
            except Exception as e:
                print("click fail", str(e)[:80])
            tab.reload(timeout=60000)
            time.sleep(5)

            # 1) 可交互控件 dump
            try:
                ui = tab.evaluate(
                    "() => { const out=[];"
                    " const els = document.querySelectorAll('button, a, [role=button], [class*=more], [class*=page], [class*=pagin], [class*=load]');"
                    " for (const e of els) { const t=(e.textContent||'').trim().slice(0,20);"
                    "   const cls=(e.className||'').toString().slice(0,60);"
                    "   if (t || cls) out.push({t:t, c:cls, href:(e.getAttribute('href')||'').slice(0,60)}); }"
                    " return out.slice(0,60); }")
                print("INTERACTIVE =", json.dumps(ui, ensure_ascii=True)[:2000])
            except Exception as e:
                print("ui dump fail", str(e)[:80])

            # 2) 直接 fetch page=1（同源，credentials include）
            try:
                r = tab.evaluate(
                    """async () => {
                      const res = await fetch('/api/galaxy/v2/creator/note/user/posted?tab=0&page=1', {credentials:'include'});
                      const txt = await res.text();
                      return {status: res.status, len: txt.length, head: txt.slice(0, 400)};
                    }""")
                print("FETCH_P1 =", json.dumps(r, ensure_ascii=True)[:900])
            except Exception as e:
                print("fetch fail", str(e)[:120])

            # 3) 已发布 tab 当前内容数量 + 卡片数
            try:
                info = tab.evaluate(
                    "() => { const cards = document.querySelectorAll('[class*=note-card]');"
                    " return {cards: cards.length, text_len: (document.body.innerText||'').length}; }")
                print("CARDS =", info)
            except Exception as e:
                print("cards fail", str(e)[:80])
        runtime._in_browser(diag, timeout=300)
        return 0
    finally:
        runtime.close()
        print("DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
