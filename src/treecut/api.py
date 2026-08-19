"""Local-only API sharing the exact same production service as the desktop UI."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import os
import threading
import time
import uuid
import logging
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from treecut.application import (
    CreativeRequest, JobJournal, ProductionService, open_job_journal, validate_test_material_access,
)
from treecut.analysis.pool import AnalysisPool
from treecut.bootstrap import bootstrap
from treecut.learning import ACTIONS, FeedbackStore
from treecut.library import Catalog
from treecut.main import status
from treecut.platform.paths import RuntimePaths
from treecut.platform.single_instance import SingleInstanceLock
from treecut.api_security import load_or_create_api_token


class ProductionPayload(BaseModel):
    selling_points: str = Field(min_length=1)
    narration: str = Field(min_length=1)
    target_duration: float = Field(default=30, ge=5, le=300)
    clip_seconds: float = Field(default=4, ge=1, le=15)
    output_mp4: bool | None = None
    output_jianying: bool | None = None
    include_test_materials: bool = False
    output_preset: str = "vertical"
    narration_speed: float = 1.0
    style: str = "natural"
    watermark_path: str = ""


class FeedbackPayload(BaseModel):
    media_id: int = Field(gt=0)
    query: str = ""
    action: str
    reason: str = ""


class CategoryPayload(BaseModel):
    category: str


class TagsPayload(BaseModel):
    tags: list[str] = Field(default_factory=list)


class LocalJobManager:
    def __init__(self, journal: JobJournal, settings=None):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="treecut-production")
        self._journal = journal
        self._settings = settings or bootstrap().settings
        self._accepting = True
        self._futures = {}
        self._session_id = uuid.uuid4().hex
        self.interrupted_count = journal.mark_interrupted(self._session_id)
        for job in journal.recent(500):
            self._jobs[job["id"]] = job

    def submit(self, payload: ProductionPayload) -> str:
        if not self._accepting:
            raise RuntimeError("TreeCut API 正在关闭，不再接收新任务")
        job_id = uuid.uuid4().hex
        payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        default_mp4, default_jianying = self._settings.output_flags()
        if payload_data.get("output_mp4") is None:
            payload_data["output_mp4"] = default_mp4
        if payload_data.get("output_jianying") is None:
            payload_data["output_jianying"] = default_jianying
        with self._lock:
            self._jobs[job_id] = {"id": job_id, "session_id": self._session_id,
                                  "state": "queued", "message": "已排队",
                                  "created_at": time.time(), "result": None, "error": None,
                                  "percent": None,
                                  "request": payload_data}
            self._journal.save(self._jobs[job_id], payload_data)
        self._futures[job_id] = self._executor.submit(self._run, job_id)
        return job_id

    def _run(self, job_id: str):
        def progress(message: str, percent: float | None = None):
            with self._lock:
                self._jobs[job_id].update(state="running", message=message, percent=percent)
                self._journal.save(self._jobs[job_id])
        try:
            with self._lock:
                payload_data = dict(self._jobs[job_id]["request"])
            request = CreativeRequest(**payload_data)
            result = ProductionService().create(request, progress)
            with self._lock:
                self._jobs[job_id].update(state="success", message="全部输出完成",
                                          result=result.to_dict())
                self._journal.save(self._jobs[job_id])
        except Exception as exc:
            logging.getLogger("treecut").exception("API production job %s failed", job_id)
            with self._lock:
                self._jobs[job_id].update(state="failed", message="制作失败",
                                          error=f"{type(exc).__name__}: {exc}")
                self._journal.save(self._jobs[job_id])

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            value = self._jobs.get(job_id)
            return dict(value) if value else self._journal.get(job_id)

    def retry(self, job_id: str) -> str:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job["state"] != "failed":
            raise ValueError("只有失败或被中断的任务可以重试")
        return self.submit(ProductionPayload(**job["request"]))

    def recent(self, limit: int = 100) -> list[dict]:
        return self._journal.recent(limit=min(max(limit, 0), 500))

    def shutdown(self) -> None:
        """Stop accepting work and truthfully fail queued jobs that never started."""
        with self._lock:
            if not self._accepting:
                return
            self._accepting = False
            now = time.time()
            for job_id, future in self._futures.items():
                if future.cancel():
                    self._jobs[job_id].update(
                        state="failed", message="API 关闭前任务尚未开始",
                        error="Shutdown: API 已关闭，请重新启动后重试", updated_at=now,
                    )
                    self._journal.save(self._jobs[job_id])
        self._executor.shutdown(wait=False, cancel_futures=True)


def validate_bind_host(host: str) -> None:
    if host.lower() not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("TreeCut API 默认只允许绑定本机地址")


def _run_analysis_loop(stop_event: threading.Event, paths: RuntimePaths) -> None:
    """Process pending analysis jobs in child processes so production model
    memory (BGE/CLIP/TTS cache) never shares the same address space."""
    catalog = Catalog(paths.databases / "materials.db")
    pool: AnalysisPool | None = None
    while not stop_event.is_set():
        try:
            if pool is None:
                pool = AnalysisPool(catalog.db_path, workers=1)
            if not catalog.pending_jobs(limit=1):
                stop_event.wait(5)
                continue
            pool.run_batch(3)
        except Exception:
            logging.getLogger("treecut").exception("API analysis loop failed")
            if pool is not None:
                try:
                    pool.close()
                except Exception:
                    pass
                pool = None
            stop_event.wait(5)
    if pool is not None:
        try:
            pool.close()
        except Exception:
            pass


def create_app() -> FastAPI:
    context = bootstrap()
    api_token = load_or_create_api_token(context.paths.data_root)
    manager = LocalJobManager(open_job_journal(context.paths.databases), context.settings)
    feedback_store = FeedbackStore(context.paths.databases / "feedback.db")

    @asynccontextmanager
    async def lifespan(_app):
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_run_analysis_loop, args=(stop_event, context.paths), daemon=True,
        )
        thread.start()
        yield
        stop_event.set()
        manager.shutdown()

    app = FastAPI(title="TreeCut v13 Local API", version="13.5.10", lifespan=lifespan)
    app.state.api_token = api_token
    app.state.api_token_path = str(context.paths.data_root / "config" / "api_token.txt")

    @app.middleware("http")
    async def require_local_token(request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        supplied = request.headers.get("X-TreeCut-Token", "")
        if not supplied or not secrets.compare_digest(supplied, api_token):
            return JSONResponse(
                status_code=401,
                content={"detail": "缺少或错误的 TreeCut 本地访问令牌"},
                headers={"WWW-Authenticate": "X-TreeCut-Token"},
            )
        return await call_next(request)

    @app.get("/health")
    def health():
        return status()

    @app.get("/catalog")
    def catalog_status():
        context = bootstrap()
        catalog = Catalog(context.paths.databases / "materials.db")
        return {"stats": catalog.stats(), "jobs": catalog.job_stats(),
                "sources": catalog.list_sources()}

    @app.get("/catalog/media")
    def catalog_media(status: str | None = None, limit: int = 500):
        catalog = Catalog(context.paths.databases / "materials.db")
        try:
            return {"items": catalog.list_media(status=status, limit=limit)}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/catalog/media/{media_id}/retry", status_code=202)
    def retry_media_analysis(media_id: int):
        catalog = Catalog(context.paths.databases / "materials.db")
        try:
            job_id = catalog.retry_analysis(media_id)
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except (ValueError, RuntimeError) as error:
            raise HTTPException(409, str(error)) from error
        return {"media_id": media_id, "analysis_job_id": job_id, "state": "pending"}

    @app.patch("/catalog/media/{media_id}/category")
    def update_media_category(media_id: int, payload: CategoryPayload):
        catalog = Catalog(context.paths.databases / "materials.db")
        try:
            catalog.set_category(media_id, payload.category)
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return {"media_id": media_id, "category": payload.category,
                "category_source": "user_override"}

    @app.patch("/catalog/media/{media_id}/tags")
    def update_media_tags(media_id: int, payload: TagsPayload):
        catalog = Catalog(context.paths.databases / "materials.db")
        try:
            catalog.set_tags(media_id, payload.tags)
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return {"media_id": media_id, "tags": payload.tags}

    @app.post("/production/jobs", status_code=202)
    def create_job(payload: ProductionPayload):
        default_mp4, default_jianying = context.settings.output_flags()
        wants_mp4 = default_mp4 if payload.output_mp4 is None else payload.output_mp4
        wants_jianying = default_jianying if payload.output_jianying is None else payload.output_jianying
        if not (wants_mp4 or wants_jianying):
            raise HTTPException(422, "至少选择一种输出")
        try:
            validate_test_material_access(payload.include_test_materials)
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        return {"job_id": manager.submit(payload), "state": "queued"}

    @app.get("/production/jobs")
    def list_jobs(limit: int = 100):
        return {"items": manager.recent(limit), "interrupted_on_startup": manager.interrupted_count}

    @app.get("/production/jobs/{job_id}")
    def get_job(job_id: str):
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(404, "任务不存在")
        return job

    @app.post("/production/jobs/{job_id}/retry", status_code=202)
    def retry_job(job_id: str):
        try:
            new_job_id = manager.retry(job_id)
        except KeyError as error:
            raise HTTPException(404, "任务不存在") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {"job_id": new_job_id, "state": "queued", "retry_of": job_id}

    @app.get("/feedback")
    def list_feedback(limit: int = 100):
        return {"items": feedback_store.list_records(limit=min(max(limit, 0), 500))}

    @app.post("/feedback", status_code=201)
    def create_feedback(payload: FeedbackPayload):
        if payload.action not in ACTIONS:
            raise HTTPException(422, "action 必须是 keep、replace 或 block")
        try:
            feedback_id = feedback_store.record(
                payload.media_id, payload.query, payload.action, payload.reason,
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return {"id": feedback_id, "accepted": True}

    return app


def main(host: str = "127.0.0.1", port: int = 8765):
    validate_bind_host(host)
    import uvicorn
    paths = RuntimePaths.discover()
    paths.apply_environment()
    with SingleInstanceLock(paths.data_root / "locks" / "api.lock"):
        uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main(
        host=os.environ.get("TREECUT_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("TREECUT_API_PORT", "8765")),
    )
