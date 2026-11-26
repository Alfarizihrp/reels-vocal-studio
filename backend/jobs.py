import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}
_lock = Lock()

# Single worker so CPU-heavy AI tasks (Whisper, audio-separator, FFmpeg) never overload CPU/RAM
executor = ThreadPoolExecutor(max_workers=1)


def create_job(job_type: str, title: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "title": title,
            "status": "queued",
            "progress": 0,
            "message": "Menunggu antrean...",
            "result": None,
            "error": None,
            "created_at": time.time(),
        }
    return job_id


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    result: Any = None,
    error: str | None = None,
) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        if status is not None:
            job["status"] = status
        if progress is not None:
            job["progress"] = progress
        if message is not None:
            job["message"] = message
        if result is not None:
            job["result"] = result
        if error is not None:
            job["error"] = error


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def list_jobs() -> list[dict[str, Any]]:
    with _lock:
        return [dict(j) for j in sorted(_jobs.values(), key=lambda x: x["created_at"], reverse=True)]
