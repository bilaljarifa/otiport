# -*- coding: utf-8 -*-
"""A minimal in-memory job registry so the frontend can show real backtest
progress instead of a blocked button. The app has no task queue (Celery,
RQ, …) and adding one just for this would be a disproportionate amount of
new infrastructure for one endpoint — a plain dict guarded by a lock, in the
same "in-memory, per-process" spirit as `backend/news_cache.py` and
`backend/market_cache.py`, is enough: one FastAPI worker process, one job
store, jobs run on a background thread and are polled by job id.

Every progress value written here comes directly from `run_backtest`'s own
`on_progress` callback — this module never invents or interpolates a
progress percentage.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Optional

from backend.backtester import BacktestError, run_backtest

_JOB_TTL_SECONDS = 15 * 60
_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _prune_expired() -> None:
    now = time.monotonic()
    expired = [jid for jid, job in _jobs.items() if now - job["created_at"] > _JOB_TTL_SECONDS]
    for jid in expired:
        _jobs.pop(jid, None)


def start_backtest_job(**run_backtest_kwargs) -> str:
    """Kicks off `run_backtest` on a background thread and returns a job id
    immediately. The caller polls `get_job` with that id."""
    with _lock:
        _prune_expired()
        job_id = uuid.uuid4().hex
        _jobs[job_id] = {
            "status": "running",
            "created_at": time.monotonic(),
            "progress": {"phase": "starting", "completed": 0, "total": 0,
                         "period_start": None, "period_end": None},
            "result": None,
            "error": None,
        }

    def on_progress(phase: str, completed: int, total: int,
                     period_start: Optional[str], period_end: Optional[str]) -> None:
        with _lock:
            job = _jobs.get(job_id)
            if job is not None:
                job["progress"] = {
                    "phase": phase, "completed": completed, "total": total,
                    "period_start": period_start, "period_end": period_end,
                }

    def _run() -> None:
        try:
            result = run_backtest(**run_backtest_kwargs, on_progress=on_progress)
            with _lock:
                job = _jobs.get(job_id)
                if job is not None:
                    job["status"] = "done"
                    job["result"] = result
        except BacktestError as exc:
            with _lock:
                job = _jobs.get(job_id)
                if job is not None:
                    job["status"] = "error"
                    job["error"] = str(exc)
        except Exception as exc:  # noqa: BLE001 - a job must always resolve, never hang forever
            with _lock:
                job = _jobs.get(job_id)
                if job is not None:
                    job["status"] = "error"
                    job["error"] = f"Backtest error: {exc}"

    threading.Thread(target=_run, daemon=True).start()
    return job_id


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job is not None else None
