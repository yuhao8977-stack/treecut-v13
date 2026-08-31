# -*- coding: utf-8 -*-
"""V0.3 — Spotlight 关键端点完整响应体捕获（redacted）→ schema 分析。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

SPOTLIGHT = "https://ad.xiaohongshu.com/aurora/ad/manage/campaign"
WANT = ("rtb/campaign/base/list", "light/campaign/data/list", "rtb/unit/base/list",
        "light/campaign/extra/list", "campaigngroup/data/list", "ad/manage/data/overall")

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
            tab = runtime.ensure_tabs().get("SPOTLIGHT")
            bodies = {}

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = response.headers.get("content-type") or ""
                    if "json" not in ctype:
                        return
                    body = response.json()
                except Exception:
                    return
                s = _safe(u)
                if any(w in s for w in WANT):
                    bodies.setdefault(s, body)

            tab.on("response", on_response)
            try:
                tab.goto(SPOTLIGHT, timeout=60000)
                time.sleep(8)
            except Exception as e:
                print(f"NAV_FAIL {str(e)[:120]}")
            try:
                tab.reload(timeout=60000)
                time.sleep(10)
            except Exception as e:
                print(f"RELOAD_FAIL {str(e)[:120]}")
            # 滚动 + 尝试点下一页
            try:
                tab.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(3)
                tab.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('button,a,[class*=page],[class*=next],[class*=pagination]'));"
                    " const n = els.find(e => /下一页|next|>/.test((e.textContent||'').trim()) || /next/.test(e.className||''));"
                    " if (n) { n.click(); return true; } return false; }")
                time.sleep(4)
            except Exception:
                pass
            tab.remove_listener("response", on_response)

            out_dir = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                           r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\spotlight_schema")
            out_dir.mkdir(parents=True, exist_ok=True)
            seen = set()
            for ep, body in bodies.items():
                name = re.sub(r"[^a-z0-9]+", "_", ep.replace("ad.xiaohongshu.com/api/leona/", "leona_")
                              .replace("ad.xiaohongshu.com/api/light/", "light_")) + ".json"
                n = 1
                base = name
                while name in seen:
                    name = base.replace(".json", f"_{n}.json")
                    n += 1
                seen.add(name)
                (out_dir / name).write_text(
                    json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"SAVED {name} ({len(json.dumps(body, ensure_ascii=False))} chars)")
            print(f"OUT_DIR = {out_dir}")
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("BODY_CAPTURE_DONE")


def _safe(url: str) -> str:
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


if __name__ == "__main__":
    sys.exit(main())
