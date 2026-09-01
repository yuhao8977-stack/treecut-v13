# -*- coding: utf-8 -*-
"""V0.6.2 枚举探针：翻完已发布列表，记录全部笔记 id/time/duration，输出 19 目标位置。"""
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
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_V062_LIST_ENUM_V1.json")
MANIFEST = json.loads(Path(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_SAMPLE20_V1.json")
                      .read_text(encoding="utf-8"))
TARGETS = {s["note_id"]: s for s in MANIFEST["samples"]}
del TARGETS["69f9a0ac000000003701d937"]          # Pilot1 已恢复，不在此枚举需求内


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
            items = []
            seen = set()

            def on_resp(resp):
                try:
                    if "creator/note/user/posted" in resp.url:
                        body = resp.body()[:6000000]
                        data = json.loads(body.decode("utf-8", errors="replace"))
                        itms = ((data.get("data") or {}).get("items")
                                or (data.get("data") or {}).get("notes") or [])
                        for it in itms:
                            nid = str(it.get("id") or it.get("noteId") or "")
                            if not nid or nid in seen:
                                continue
                            seen.add(nid)
                            vi = str(it.get("video_info") or "")
                            m = re.search(r"duration['\"]?\s*[:=]\s*(\d+)", vi)
                            items.append({"id": nid,
                                          "time": str(it.get("time") or "")[:16],
                                          "duration": int(m.group(1)) if m else None,
                                          "title": str(it.get("display_title") or "")[:60]})
                except Exception:
                    pass

            tab.on("response", on_resp)
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(10)
            # 点击「已发布」tab（语义文本）
            try:
                tab.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('div,span,li,a,button'));"
                    " const t = els.find(e => (e.textContent||'').trim() === '已发布' && e.children.length <= 2);"
                    " if (t) { t.click(); return true; } return false; }")
                time.sleep(2)
            except Exception:
                pass
            last = 0
            stall = 0
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
                if len(items) > last:
                    last = len(items)
                    stall = 0
                else:
                    stall += 1
                    if stall >= 3:
                        break
                if rnd % 25 == 0:
                    safe_print(f"  [enum] round={rnd} items={len(items)}")
            # 输出
            pos = {}
            for i, it in enumerate(items):
                if it["id"] in TARGETS:
                    pos[it["id"]] = {"index": i, "time": it["time"], "duration": it["duration"],
                                     "title": it["title"]}
            missing = [nid for nid in TARGETS if nid not in pos]
            safe_print(f"TOTAL_ITEMS={len(items)} targets_found={len(pos)} missing={len(missing)}")
            for nid in sorted(pos, key=lambda x: pos[x]["index"]):
                safe_print(f"  FOUND idx={pos[nid]['index']} {nid} {pos[nid]['time']} dur={pos[nid]['duration']}")
            for nid in missing:
                safe_print(f"  MISSING {nid} {TARGETS[nid]['title'][:30]}")
            OUT.write_text(json.dumps(
                {"total": len(items), "positions": pos, "missing": missing,
                 "sample": [it for it in items]},
                ensure_ascii=False, indent=1), encoding="utf-8")
            return {"total": len(items), "found": len(pos), "missing": missing}

        r = runtime._in_browser(probe, timeout=1500)
        safe_print(f"ENUM_DONE total={r['total']} found={r['found']} missing={r['missing']}")
        return 0
    finally:
        runtime.close()
        safe_print("ENUM_CLOSED")


if __name__ == "__main__":
    sys.exit(main())
