"""Submit four real local production jobs and wait for independent results."""
from __future__ import annotations

import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = "http://127.0.0.1:8767"
REQUESTS = [
    {
        "selling_points": "岛台产品展示，伸缩设计，分区收纳",
        "narration": "灵活伸缩的岛台，让小空间兼顾收纳、备餐和用餐。",
        "target_duration": 5, "clip_seconds": 2,
        "output_mp4": True, "output_jianying": True,
        "include_test_materials": True,
    },
    {
        "selling_points": "客户案例，家庭聚餐，实用岛台",
        "narration": "真实家庭案例，岛台让日常用餐和亲友聚会更加从容。",
        "target_duration": 5, "clip_seconds": 2,
        "output_mp4": True, "output_jianying": False,
        "include_test_materials": True,
    },
    {
        "selling_points": "厨房室内空间，岛台布局，收纳",
        "narration": "合理的厨房动线配合岛台布局，让空间整洁又实用。",
        "target_duration": 5, "clip_seconds": 2,
        "output_mp4": False, "output_jianying": True,
        "include_test_materials": True,
    },
    {
        "selling_points": "产品展示，实用尺寸，办公和聚餐",
        "narration": "合适的尺寸让岛台既能办公，也能满足一家人的聚餐需求。",
        "target_duration": 5, "clip_seconds": 2,
        "output_mp4": True, "output_jianying": True,
        "include_test_materials": True,
    },
]


def request_json(method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    request = Request(BASE + path, data=data, method=method,
                      headers={"Content-Type": "application/json; charset=utf-8"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    started = time.time()
    jobs = []
    for lane, payload in enumerate(REQUESTS, 1):
        response = request_json("POST", "/production/jobs", payload)
        jobs.append({"lane": lane, "id": response["job_id"], "last_state": response["state"]})
        print(f"lane={lane} job={response['job_id']} state={response['state']}", flush=True)
    terminal = {"success", "failed"}
    while any(job["last_state"] not in terminal for job in jobs):
        for job in jobs:
            if job["last_state"] in terminal:
                continue
            state = request_json("GET", f"/production/jobs/{job['id']}")
            if state["state"] != job["last_state"]:
                print(f"lane={job['lane']} state={state['state']} message={state['message']}", flush=True)
                job["last_state"] = state["state"]
            job["result"] = state.get("result")
            job["error"] = state.get("error")
        time.sleep(1)
    summary = {
        "elapsed_seconds": round(time.time() - started, 2),
        "success": sum(job["last_state"] == "success" for job in jobs),
        "failed": sum(job["last_state"] == "failed" for job in jobs),
        "jobs": jobs,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    if summary["success"] != 4:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        print(error.read().decode("utf-8", errors="replace"))
        raise
