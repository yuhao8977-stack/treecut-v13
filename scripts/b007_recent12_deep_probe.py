# -*- coding: utf-8 -*-
"""探针：深滚后目标笔记(6a659145, 2026-07-26)的 DOM 卡是否存在。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"
TARGET = "6a659145000000001101f9be"


def safe_print(m):
    try:
        print(m)
    except Exception:
        print(m.encode("gbk", errors="replace").decode("gbk"))


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
            tab = runtime.ensure_tabs().get("CREATOR")
            ctx = runtime._context
            api_item = {}

            def on_resp(resp):
                try:
                    if "creator/note/user/posted" in resp.url:
                        body = resp.body()[:6000000]
                        data = json.loads(body.decode("utf-8", errors="replace"))
                        itms = ((data.get("data") or {}).get("items")
                                or (data.get("data") or {}).get("notes") or [])
                        for it in itms:
                            if str(it.get("id") or "") == TARGET:
                                api_item.update({k: str(v)[:60] for k, v in it.items()})
                except Exception:
                    pass

            tab.on("response", on_resp)
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(10)
            try:
                tab.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('div,span,li,a,button'));"
                    " const t = els.find(e => (e.textContent||'').trim() === '已发布' && e.children.length <= 2);"
                    " if (t) { t.click(); return true; } return false; }")
                time.sleep(2)
            except Exception:
                pass
            for rnd in range(400):
                try:
                    tab.evaluate(
                        """() => {
                          const els = Array.from(document.querySelectorAll('*'));
                          const sc = els.filter(e => e.scrollHeight > e.clientHeight + 100
                            && getComputedStyle(e).overflowY !== 'visible');
                          for (const e of sc) e.scrollTop = e.scrollHeight;
                          window.scrollTo(0, document.body.scrollHeight);
                        }""")
                except Exception:
                    pass
                time.sleep(2.2)
                if api_item:
                    safe_print(f"API_FOUND round={rnd} time={api_item.get('time')}")
                    break
                if rnd % 30 == 0:
                    safe_print(f"  round={rnd}")
            time.sleep(4)
            st = tab.evaluate(
                """() => {
                  const all = Array.from(document.querySelectorAll('[class*=note-card]'));
                  const hits_date = [];
                  const hits_title = [];
                  for (let i=0;i<all.length;i++){
                    const r = all[i].getBoundingClientRect();
                    if (r.width<=200 || r.height<=50) continue;
                    const txt = (all[i].innerText||'').replace(/\\n+/g,'|');
                    if (txt.indexOf('2026-07-26') >= 0 && hits_date.length < 3) hits_date.push({i, s: txt.slice(0,120)});
                    if (txt.indexOf('13个尺寸') >= 0 && hits_title.length < 3) hits_title.push({i, s: txt.slice(0,120)});
                  }
                  return {total: all.length, hits_date, hits_title};
                }""")
            safe_print("API_ITEM=" + json.dumps(api_item, ensure_ascii=True))
            safe_print("DOM=" + json.dumps(st, ensure_ascii=True))
            return {"api": api_item, "dom": st}

        runtime._in_browser(probe, timeout=1500)
        safe_print("PROBE_DONE")
        return 0
    finally:
        runtime.close()
        safe_print("PROBE_CLOSED")


if __name__ == "__main__":
    sys.exit(main())
