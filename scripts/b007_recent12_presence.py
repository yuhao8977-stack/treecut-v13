# -*- coding: utf-8 -*-
"""预校验：一次全列表 sweep，确认 Recent12 剩余笔记在已发布列表中的存在性。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"
CHECK = ["6a659145000000001101f9be",   # 已疑似缺失
         "6a411feb000000001c026d77", "6a411f31000000001503cdc6",
         "6a37dcbf0000000007010e07", "6a37da9d00000000080311af",
         "6a369c78000000000702e481", "6a2bb62d00000000070200a5"]
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_RECENT12_PRESENCE_CHECK_V1.json")


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
            seen = {}
            dom_seen = {}

            def on_resp(resp):
                try:
                    if "creator/note/user/posted" in resp.url:
                        body = resp.body()[:6000000]
                        data = json.loads(body.decode("utf-8", errors="replace"))
                        itms = ((data.get("data") or {}).get("items")
                                or (data.get("data") or {}).get("notes") or [])
                        for it in itms:
                            nid = str(it.get("id") or "")
                            if nid in CHECK:
                                seen[nid] = str(it.get("time") or "")[:16]
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
                if rnd % 40 == 0:
                    safe_print(f"  round={rnd} api_seen={sorted(seen)}")
                if all(nid in seen for nid in CHECK):
                    break
                if rnd % 40 == 0 and rnd > 0 and len(seen) == 0 and rnd == 360:
                    safe_print("  ...")
            time.sleep(3)
            # DOM 校验（标题/时间片段）
            titles = {"6a659145000000001101f9be": ["13个尺寸做对"],
                      "6a411feb000000001c026d77": ["尺寸避坑"],
                      "6a411f31000000001503cdc6": ["岩板操作台"],
                      "6a37dcbf0000000007010e07": ["意式简约岛台"],
                      "6a37da9d00000000080311af": ["避坑"],
                      "6a369c78000000000702e481": ["2.8米伸缩岛台"],
                      "6a2bb62d00000000070200a5": ["集成用电"]}
            dom = tab.evaluate(
                """(pairs) => {
                  const all = Array.from(document.querySelectorAll('[class*=note-card]'));
                  const out = {};
                  const keys = Object.keys(pairs);
                  for (let i=0;i<all.length;i++){
                    const r = all[i].getBoundingClientRect();
                    if (r.width<=200 || r.height<=50) continue;
                    const txt = (all[i].innerText||'').replace(/\\n+/g,'|');
                    for (const k of keys) {
                      if (out[k]) continue;
                      for (const frag of pairs[k]) {
                        if (txt.indexOf(frag) >= 0) { out[k] = txt.slice(0,100); break; }
                      }
                    }
                  }
                  return out;
                }""", titles)
            safe_print("API_SEEN=" + json.dumps(seen, ensure_ascii=True))
            safe_print("DOM_HITS=" + json.dumps(dom, ensure_ascii=True))
            res = {nid: {"api_seen": nid in seen, "api_time": seen.get(nid),
                         "dom_hit": nid in dom, "dom_sample": dom.get(nid)} for nid in CHECK}
            OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            return res

        runtime._in_browser(probe, timeout=1800)
        safe_print("PROBE_DONE")
        return 0
    finally:
        runtime.close()
        safe_print("PROBE_CLOSED")


if __name__ == "__main__":
    sys.exit(main())
