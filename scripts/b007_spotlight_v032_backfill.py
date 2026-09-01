# -*- coding: utf-8 -*-
"""V0.3.2 — 月度历史 Note Paid Metrics 回填（互不重叠自然月 2026-04..08）。

每窗口：
  - 笔记报表 → 页大小 100 → 自定义日期区间 → 下一页点击穷尽（next disabled 止）
  - 证据：spotlight_raw_v032/<run>/<WINDOW>/（redacted + sha256）
  - checkpoint：每窗口完成写 checkpoint.json（可 resume）
NOTE_REPORT_EXHAUSTED 判定：next 按钮 disabled 或 连续 3 轮无新页。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_REPORT = "https://ad.xiaohongshu.com/aurora/ad/datareports-basic/note"
MONTHS = [
    ("M2026-04", "2026-04-01", "2026-04-30"),
    ("M2026-05", "2026-05-01", "2026-05-31"),
    ("M2026-06", "2026-06-01", "2026-06-30"),
    ("M2026-07", "2026-07-01", "2026-07-31"),
    ("M2026-08", "2026-08-01", "2026-08-31"),
]
SENSITIVE = re.compile(r"(token|sign|cookie|authorization|x-s|x-t|credential)", re.I)


def redact(node):
    if isinstance(node, dict):
        return {k: redact(v) for k, v in node.items() if not SENSITIVE.search(k)}
    if isinstance(node, list):
        return [redact(x) for x in node]
    if isinstance(node, str):
        return re.sub(r"([?&](xsec_token|xsec_source|x-s|x-t|sign)=)[^&\s]+", r"\1REDACTED", node)
    return node


def set_page_size(tab) -> bool:
    try:
        tab.locator(".d-select-wrapper").first.click(timeout=8000, force=True)
        time.sleep(2)
        r = tab.evaluate(
            """() => {
              const els = Array.from(document.querySelectorAll('[class*=select-option], [class*=dropdown] li, [class*=dropdown] div'));
              const t = els.find(e => (e.textContent||'').trim() === '100 条/页');
              if (t) { t.click(); return true; }
              return false;
            }""")
        time.sleep(4)
        # 确保下拉关闭
        try:
            tab.keyboard.press("Escape")
            time.sleep(1)
        except Exception:
            pass
        return bool(r)
    except Exception:
        return False


def set_custom_range(tab, start: str, end: str) -> bool:
    try:
        # 先关闭可能的残留下拉
        try:
            tab.keyboard.press("Escape")
            time.sleep(1)
        except Exception:
            pass
        tab.locator(".d-daterangepicker-content, .report-date-range-picker").first.click(timeout=8000, force=True)
        time.sleep(2.5)
        r = tab.evaluate(
            """(d) => {
              const ins = Array.from(document.querySelectorAll('.d-daterangepicker input.d-text, .d-daterangepicker-input-filter input'));
              if (ins.length >= 2) {
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(ins[0], d.start); ins[0].dispatchEvent(new Event('input', {bubbles:true}));
                setter.call(ins[1], d.end); ins[1].dispatchEvent(new Event('input', {bubbles:true}));
                return true;
              }
              return false;
            }""", {"start": start, "end": end})
        time.sleep(2)
        # 触发查询：Enter 或 点确定/关闭
        try:
            tab.keyboard.press("Enter")
            time.sleep(2)
        except Exception:
            pass
        ok = tab.evaluate(
            """() => {
              const els = Array.from(document.querySelectorAll('button,[class*=confirm],[class*=ok],[class*=submit]'));
              const b = els.find(e => /确定|完成|查询/.test((e.textContent||'').trim()) && e.getBoundingClientRect().width > 0);
              if (b) { b.click(); return true; }
              return false;
            }""")
        time.sleep(2)
        try:
            tab.evaluate("() => { const el=document.activeElement; if (el) el.blur(); document.body.click(); }")
            time.sleep(3)
        except Exception:
            pass
        return bool(r)
    except Exception:
        return False


def active_page(tab):
    try:
        r = tab.evaluate(
            """() => {
              const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
              for (const p of pages) {
                if (/bg-prima|active|current/i.test(p.className||'')) {
                  const sp = p.querySelector('span');
                  const raw = sp ? (sp.textContent||'').trim() : '';
                  const m = raw.match(/\\d+/);
                  return m ? parseInt(m[0], 10) : null;
                }
              }
              return null;
            }""")
        return r
    except Exception:
        return None


def click_exact(tab, n: int) -> bool:
    """精确匹配 span 文本 == str(n)（避免 has_text 子串误匹配两位数）。"""
    try:
        return bool(tab.evaluate(
            """(n) => {
              const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
              for (const p of pages) {
                const sp = p.querySelector('span');
                const raw = sp ? (sp.textContent||'').trim() : '';
                if (raw === String(n)) { p.click(); return true; }
              }
              return false;
            }""", n))
    except Exception:
        return False


def click_ellipsis(tab) -> bool:
    try:
        return bool(tab.evaluate(
            """() => {
              const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
              for (const p of pages) {
                if ((p.textContent||'').trim() === '...') { p.click(); return true; }
              }
              return false;
            }"""))
    except Exception:
        return False


def report_total(tab):
    try:
        r = tab.evaluate(
            "() => { const p=document.querySelector('.d-pagination');"
            " const m = p ? (p.textContent||'').match(/共\\s*(\\d+)\\s*条/) : null; return m ? parseInt(m[1],10) : 0; }")
        return r or 0
    except Exception:
        return 0


def capture_window(tab, out_dir: Path, setup_fn=None, max_rounds=300) -> dict:
    """监听器全程挂载（setup_fn 在监听后执行：页大小+日期设置），再分页穷尽。"""
    bodies = {}
    pages_seen = set()
    nonlocal_vars = [0]

    def on_response(response):
        try:
            u = response.url or ""
            ctype = response.headers.get("content-type") or ""
            if "json" not in ctype or "rtb/common/data/report" not in u:
                return
            body = response.json()
        except Exception:
            return
        data = body.get("data")
        if not isinstance(data, dict):
            return
        pn = (data.get("page") or {}).get("pageIndex")
        if pn is not None and pn not in pages_seen:
            pages_seen.add(pn)
            bodies[f"report#p{pn}"] = redact(body)
            nonlocal_vars[0] = max(nonlocal_vars[0], pn or 0)

    tab.on("response", on_response)
    if setup_fn:
        setup_fn()
        time.sleep(4)
    # 先回到第 1 页（精确匹配，避免继承历史页状态），然后清空缓冲（丢弃设置期脏数据）
    try:
        click_exact(tab, 1)
        time.sleep(4)
    except Exception:
        pass
    bodies.clear()
    pages_seen.clear()
    nonlocal_vars[0] = 0
    no_new = 0
    exhausted = False
    cur = active_page(tab) or 1
    for it in range(max_rounds):
        before = len(bodies)
        target = (cur or 1) + 1
        # 精确点 target；不可见则点省略号推进窗口
        clicked = click_exact(tab, target)
        if not clicked:
            clicked = click_ellipsis(tab)
        advanced = False
        if clicked:
            for _w in range(10):
                time.sleep(1.0)
                np = active_page(tab)
                if np is not None and np > (cur or 1):
                    cur = np
                    advanced = True
                    break
                if len(bodies) > before:
                    np2 = active_page(tab)
                    if np2:
                        cur = np2
                    advanced = True
                    break
        if len(bodies) > before or advanced:
            no_new = 0
        else:
            no_new += 1
            if no_new >= 3:
                print(f"  no progress after {it + 1} rounds (page {cur}, target {target})")
                break
        if cur is not None and cur >= ((report_total(tab) + 99) // 100) and report_total(tab) > 0:
            # 已到最后页
            for _w in range(8):
                time.sleep(1.0)
                if len(bodies) > before:
                    break
            print(f"  reached last page {cur} after {it + 1} rounds")
            exhausted = True
            break
    # 兜底：确保最后一页已捕获
    try:
        before = len(bodies)
        total = report_total(tab)
        last_idx = (total + 99) // 100 if total else 0
        if last_idx > 1 and click_exact(tab, last_idx):
            for _w in range(12):
                time.sleep(1.0)
                if len(bodies) > before:
                    break
            if len(bodies) > before:
                exhausted = True
    except Exception:
        pass
    tab.remove_listener("response", on_response)
    for key, body in bodies.items():
        f = out_dir / f"{key.replace('#', '_')}.json"
        f.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
        (out_dir / (f.name + ".sha256")).write_text(hashlib.sha256(f.read_bytes()).hexdigest(), encoding="utf-8")
    return {"bodies": len(bodies), "max_page": nonlocal_vars[0], "exhausted": exhausted}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-months", type=int, default=99)
    args = ap.parse_args(argv)
    months = MONTHS[: args.max_months]
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
        base = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                    r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\spotlight_raw_v032")
        run_dir = base / time.strftime("%Y%m%d_%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = run_dir / "checkpoint.json"
        done = {}
        if checkpoint.exists():
            done = json.loads(checkpoint.read_text(encoding="utf-8"))

        def run_all():
            tab = runtime.ensure_tabs().get("SPOTLIGHT")
            prev_month_total = None
            for wkey, start, end in months:
                if wkey in done and done[wkey].get("status") == "DONE":
                    print(f"=== {wkey} already done, skip ===")
                    continue
                out_dir = run_dir / wkey
                out_dir.mkdir(parents=True, exist_ok=True)
                print(f"=== {wkey} ({start}~{end}) ===")
                try:
                    tab.goto(NOTE_REPORT, timeout=60000)
                    time.sleep(7)
                    # 日期应用验证：totalCount 必须不同于上月（否则重试日期设置，最多 3 次）
                    res = None
                    for _t in range(3):
                        def setup():
                            set_page_size(tab)
                            set_custom_range(tab, start, end)
                        res = capture_window(tab, out_dir, setup_fn=setup)
                        t = report_total(tab)
                        print(f"  attempt {_t + 1}: total={t} bodies={res['bodies']}")
                        if prev_month_total is None or t != prev_month_total:
                            prev_month_total = t
                            break
                        print("  total unchanged from previous month; retrying date set")
                        time.sleep(3)
                    # 验证输入框
                    try:
                        ins = tab.evaluate(
                            "() => Array.from(document.querySelectorAll('input.d-text, .d-daterangepicker input'))"
                            ".map(i => i.value).filter(v => /^\\d{4}-/.test(v))")
                        print(f"  date_inputs = {ins}")
                    except Exception:
                        pass
                    res["window"] = wkey
                    res["report_start"] = start
                    res["report_end"] = end
                    res["capture_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    res["status"] = "DONE"
                    done[wkey] = res
                    checkpoint.write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"  {wkey}: {res}")
                except Exception as e:
                    done[wkey] = {"status": "FAILED", "error": str(e)[:200]}
                    checkpoint.write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"  {wkey}: FAILED {str(e)[:150]}")
            return done

        results = runtime._in_browser(run_all, timeout=3600)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    finally:
        runtime.close()
        print("V032_BACKFILL_DONE")


if __name__ == "__main__":
    sys.exit(main())
