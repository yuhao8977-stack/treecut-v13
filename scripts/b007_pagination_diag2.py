# -*- coding: utf-8 -*-
"""诊断2：note-manager 已发布 tab — 容器滚动触发分页？卡片总数？"""
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
            seen_ids = set()
            hits = []

            def on_response(response):
                try:
                    u = response.url or ""
                    if "/note/user/posted" not in u:
                        return
                    body = response.json()
                    m = re.search(r"page=(\d+)", u)
                    page = int(m.group(1)) if m else 0
                    n = 0
                    for nt in (body.get("data") or {}).get("notes", []) or []:
                        nid = nt.get("id") or nt.get("note_id")
                        if nid:
                            seen_ids.add(nid)
                            n += 1
                    hits.append({"page": page, "notes": n, "total_seen": len(seen_ids)})
                    print(f"  [POSTED] page={page} notes={n} total_seen={len(seen_ids)}")
                except Exception:
                    pass

            tab.on("response", on_response)
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(4)
            try:
                tab.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('div,span,li,a,button'));"
                    " const t = els.find(e => (e.textContent||'').trim() === '已发布' && e.children.length <= 2);"
                    " if (t) { t.click(); return true; } return false; }")
                time.sleep(2)
            except Exception as e:
                print("click fail", str(e)[:80])
            tab.reload(timeout=60000)
            time.sleep(6)

            # 找滚动容器
            try:
                cont = tab.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('*'));"
                    " const sc = els.filter(e => e.scrollHeight > e.clientHeight + 100"
                    "   && getComputedStyle(e).overflowY !== 'visible');"
                    " return sc.slice(0,8).map(e => ({tag: e.tagName, cls: (e.className||'').toString().slice(0,70),"
                    "   sh: e.scrollHeight, ch: e.clientHeight})); }")
                print("SCROLL_CONTAINERS =", json.dumps(cont, ensure_ascii=True))
            except Exception as e:
                print("cont fail", str(e)[:80])

            # 容器滚动：依次滚到各容器底部
            for it in range(25):
                before = len(seen_ids)
                try:
                    tab.evaluate(
                        "() => { const els = Array.from(document.querySelectorAll('*'));"
                        " const sc = els.filter(e => e.scrollHeight > e.clientHeight + 100"
                        "   && getComputedStyle(e).overflowY !== 'visible');"
                        " for (const e of sc) e.scrollTop = e.scrollHeight;"
                        " window.scrollTo(0, document.body.scrollHeight); }")
                except Exception:
                    pass
                time.sleep(2.0)
                if len(seen_ids) <= before:
                    if it >= 3:
                        break
            print("FINAL_SEEN_IDS =", len(seen_ids))
            # 卡片数 + 可见标题
            try:
                info = tab.evaluate(
                    "() => { const cards = Array.from(document.querySelectorAll('[class*=note-card]'));"
                    " const titles = [];"
                    " for (let i=0;i<Math.min(cards.length,8);i++){"
                    "   const t = cards[i].querySelector('[class*=title]');"
                    "   titles.push(t ? (t.textContent||'').trim().slice(0,40) : ''); }"
                    " return {count: cards.length, titles: titles}; }")
                print("CARDS =", json.dumps(info, ensure_ascii=True)[:800])
            except Exception as e:
                print("cards fail", str(e)[:80])
            tab.remove_listener("response", on_response)
        runtime._in_browser(diag, timeout=400)
        return 0
    finally:
        runtime.close()
        print("DIAG2_DONE")


if __name__ == "__main__":
    sys.exit(main())
