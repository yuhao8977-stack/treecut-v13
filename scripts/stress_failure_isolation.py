"""Prove one failed queued job does not prevent the following job from running."""
from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen


BASE = "http://127.0.0.1:8767"


def call(method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    request = Request(BASE + path, data=data, method=method,
                      headers={"Content-Type": "application/json; charset=utf-8"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def submit(selling_points: str) -> str:
    payload = {
        "selling_points": selling_points,
        "narration": "这是任务隔离和队列恢复测试。",
        "target_duration": 5, "clip_seconds": 2,
        "output_mp4": False, "output_jianying": True,
        "include_test_materials": True,
    }
    return call("POST", "/production/jobs", payload)["job_id"]


def main() -> None:
    jobs = [
        ("before", submit("岛台伸缩收纳")),
        ("expected_failure", submit("量子火箭发动机海底矿井")),
        ("after", submit("厨房岛台家庭聚餐")),
    ]
    states = {}
    while len(states) < len(jobs):
        for label, job_id in jobs:
            if label in states:
                continue
            job = call("GET", f"/production/jobs/{job_id}")
            if job["state"] in {"success", "failed"}:
                states[label] = {"state": job["state"], "error": job.get("error"),
                                 "result": job.get("result")}
                print(label, job["state"], job.get("error"), flush=True)
        time.sleep(1)
    print(json.dumps(states, ensure_ascii=False, indent=2), flush=True)
    if [states[name]["state"] for name in ("before", "expected_failure", "after")] != [
        "success", "failed", "success",
    ]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
