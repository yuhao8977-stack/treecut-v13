# -*- coding: utf-8 -*-
"""V0.6.1 — 接管诊断：检查浏览器各 tab 状态（用户点击后详情页是否打开/卡住）+ 挂载观察器接管。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

TARGET = "69f9a0ac000000003701d937"


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
        runtime.reconcile_tabs()

        def probe():
            ctx = runtime._context
            print("PAGES =", len(ctx.pages))
            for i, p in enumerate(ctx.pages):
                try:
                    print(f"  [{i}] url={p.url[:130]}")
                except Exception as e:
                    print(f"  [{i}] url error {str(e)[:60]}")
                try:
                    info = p.evaluate(
                        """() => {
                          const v = document.querySelector('video');
                          return {text_len: (document.body.innerText||'').length,
                                  has_video: !!v,
                                  video_src: v && v.currentSrc ? v.currentSrc.slice(0,90) : null,
                                  title: (document.title||'').slice(0,60)};
                        }""")
                    print(f"      {json.dumps(info, ensure_ascii=True)}")
                except Exception as e:
                    print(f"      eval err {str(e)[:80]}")
        runtime._in_browser(probe, timeout=200)
        return 0
    finally:
        runtime.close()
        print("TAKEOVER_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
