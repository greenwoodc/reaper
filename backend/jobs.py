"""In-memory background job registry for the Flask backend.

Deliberately not Celery/Redis — this is a single-user local tool, and a
thread per job is more than enough. Jobs live only as long as the Flask
process does, which matches how the rest of Reaper already treats state
(everything durable lives in playlists/<slug>/ on disk instead).
"""

import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Job:
    id: str
    kind: str  # "scan" | "download" | "finalize"
    playlist_slug: str
    playlist_name: str = ""
    status: str = "queued"  # queued | running | awaiting_confirmation | done | error
    phase: str = ""
    current: int = 0
    total: int = 0
    message: str = ""
    result: Optional[dict] = None
    error: Optional[str] = None
    log: list = field(default_factory=list)

    def append_log(self, line: str, max_lines: int = 500) -> None:
        self.log.append(line)
        if len(self.log) > max_lines:
            del self.log[0]

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "playlist_slug": self.playlist_slug,
            "playlist_name": self.playlist_name,
            "status": self.status,
            "phase": self.phase,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "result": self.result,
            "error": self.error,
        }


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, kind: str, playlist_slug: str, playlist_name: str = "") -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            kind=kind,
            playlist_slug=playlist_slug,
            playlist_name=playlist_name or playlist_slug,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def run_in_background(self, job: Job, target: Callable[..., Any], *args, **kwargs) -> threading.Thread:
        def _wrapper():
            job.status = "running"
            try:
                target(job, *args, **kwargs)
                if job.status == "running":
                    job.status = "done"
            except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
                job.status = "error"
                job.error = str(exc)
                job.append_log(traceback.format_exc())

        thread = threading.Thread(target=_wrapper, daemon=True)
        thread.start()
        return thread


jobs = JobManager()
