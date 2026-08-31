# -*- coding: utf-8 -*-
"""V0.2 — Creator 页面绑定验证 + galaxy posted 响应捕获探针。

按用户指示（B003 已验证路线）：
1. 验证 Playwright 绑定的 CREATOR Page 是否就是用户看到的 note-manager
   （输出 url/title/frame 数 + 截图，截图与用户肉眼页面对比）
2. 监听页面自发的 /api/galaxy/v2/creator/note/user/posted 响应（不构造请求）
3. 挂载后 reload 页面 / 切换 Tab 触发网页自身请求 → 捕获 data.notes[] 安全字段
4. DOM 只用于 Page Ready 验证（note-card 数量 + 前 5 卡 textContent）
"""
from __future__ import annotations

import sys
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
    print("== B007 CREATOR PAGE VERIFY + POSTED CAPTURE ==")
    try:
        runtime.workspace.acquire_lock()
    except RuntimeError as error:
        print(f"PROFILE_LOCKED: {error}")
        return 2
    try:
        runtime.start_browser(headless=False)
        reconcile = runtime.reconcile_tabs()
        print("tabs_after_reconcile =", reconcile["actual"])

        def verify_and_capture():
            import time as _t
            tab = runtime.ensure_tabs().get("CREATOR")
            print("CREATOR page.url =", tab.url)
            print("CREATOR page.title =", tab.title() if hasattr(tab, "title") else "?")
            print("frames =", len(tab.frames))
            print("pages_total =", len(runtime._context.pages))

            hits = []
            note_cards = {"count": 0, "first_titles": []}

            def on_response(response):
                try:
                    url = response.url or ""
                except Exception:
                    return
                low = url.lower()
                if "galaxy" in low or "posted" in low or "note/user" in low:
                    try:
                        body = response.json()
                    except Exception:
                        body = None
                    hits.append({"url": url[:200], "status": response.status,
                                 "has_json": body is not None})
                    print(f"  [POSTED] {url[:160]} status={response.status} json={body is not None}")
                    if body:
                        # 提取 data.notes[] 安全字段
                        import json as _json
                        def scan(node):
                            found = []
                            def walk(n):
                                if not isinstance(n, dict):
                                    if isinstance(n, list):
                                        for x in n: walk(x)
                                    return
                                nid = n.get("id") or n.get("note_id")
                                import re
                                if isinstance(nid, str) and re.fullmatch(r"[0-9a-f]{24}", nid):
                                    found.append({
                                        "note_id": nid,
                                        "title": (n.get("display_title") or n.get("title") or "")[:60],
                                        "time": n.get("time"),
                                        "type": n.get("type"),
                                        "duration": (n.get("video_info") or {}).get("duration")
                                        if isinstance(n.get("video_info"), dict) else None,
                                    })
                                for v in n.values():
                                    walk(v)
                            walk(node)
                            return found
                        notes = scan(body)
                        print(f"  -> notes in response: {len(notes)}")
                        for nt in notes[:5]:
                            print("     ", nt)

            tab.on("response", on_response)

            # 挂载后 reload，触发页面自身 posted 请求（listener 在请求前）
            print("reloading note-manager with listener attached…")
            tab.goto(NOTE_MANAGER, timeout=60000)
            _t.sleep(4)
            tab.reload(timeout=60000)
            _t.sleep(8)

            # 切换 Tab（全部/已发布）尝试触发更多请求
            try:
                tab.evaluate(
                    "() => { const t = document.querySelector('[class*=tab-item]');"
                    " if (t) t.click(); }")
                _t.sleep(5)
            except Exception:
                pass

            # Page Ready 验证：DOM 卡片数 + 前 5 标题（不做 24hex 硬要求）
            try:
                info = tab.evaluate(
                    "() => { const cards = document.querySelectorAll('[class*=note-card]');"
                    " const titles = [];"
                    " for (let i=0;i<Math.min(cards.length,5);i++){"
                    "   const t = cards[i].querySelector('[class*=note-card__title]');"
                    "   titles.push(t ? (t.textContent||'').trim().slice(0,50) : ''); }"
                    " return { count: cards.length, titles: titles,"
                    "          text_len: (document.body.innerText||'').length }; }")
                note_cards = info
            except Exception as error:
                note_cards = {"count": "?", "error": str(error)[:80]}

            # 截图（与用户肉眼页面对比）
            shot = runtime.paths.data_root / "diag" / "creator_note_manager_shot.png"
            shot.parent.mkdir(parents=True, exist_ok=True)
            try:
                tab.screenshot(path=str(shot), full_page=False)
                print("SCREENSHOT =", shot)
            except Exception as error:
                print("screenshot failed:", str(error)[:120])

            print("note_cards(diag) =", note_cards)
            print("posted_hits =", len(hits))
            return {"url": tab.url, "title": (tab.title() if hasattr(tab, "title") else "?"),
                    "frames": len(tab.frames), "shot": str(shot)}

        result = runtime._in_browser(verify_and_capture)
        print("---- RESULT ----")
        for k, v in result.items():
            print(f"{k} = {v}")
        return 0
    finally:
        runtime.close()
        print("VERIFY_PROBE_DONE")


if __name__ == "__main__":
    sys.exit(main())
