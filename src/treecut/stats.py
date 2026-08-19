"""Collect one snapshot of catalog, job, project and feedback statistics."""
from __future__ import annotations

from collections import Counter
from statistics import mean

from treecut.application import open_job_journal
from treecut.bootstrap import AppContext
from treecut.learning import FeedbackStore
from treecut.library import Catalog


def collect_stats(context: AppContext) -> dict:
    catalog = Catalog(context.paths.databases / "materials.db")
    jobs = open_job_journal(context.paths.databases).recent(500)
    projects_dir = context.paths.output / "projects"
    project_count = len([item for item in projects_dir.glob("*") if item.is_dir()]) if projects_dir.is_dir() else 0
    feedback_count = len(FeedbackStore(context.paths.databases / "feedback.db").list_records(500))
    durations = [
        float(job["updated_at"] - job["created_at"])
        for job in jobs
        if job.get("updated_at") and job.get("created_at") and job["state"] == "success"
    ]
    failed = Counter(job["state"] for job in jobs)
    total = max(1, len(jobs))
    return {
        "sources": catalog.stats(),
        "analysis": catalog.job_stats(),
        "production_jobs": dict(Counter(job["state"] for job in jobs)),
        "projects": project_count,
        "feedback_records": feedback_count,
        "production_stats": {
            "success": failed.get("success", 0),
            "failed": failed.get("failed", 0),
            "failure_rate": round(failed.get("failed", 0) / total * 100, 1),
            "avg_seconds": round(mean(durations), 1) if durations else 0.0,
            "max_seconds": round(max(durations), 1) if durations else 0.0,
        },
        "model_plan": context.model_plan.to_dict(),
    }
