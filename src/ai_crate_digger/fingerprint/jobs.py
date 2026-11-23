"""Background jobs for work that outlasts a single MCP tool call."""

import logging
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Literal

from ai_crate_digger.fingerprint.indexer import IndexReport
from ai_crate_digger.fingerprint.matcher import MixResult

logger = logging.getLogger(__name__)

JobKind = Literal["index", "mix"]
JobStatus = Literal["queued", "running", "done", "failed"]
ProgressFn = Callable[[float], None]
Work = Callable[[ProgressFn], MixResult | IndexReport]


@dataclass
class Job:
    """State of one background job."""

    job_id: str
    kind: JobKind
    label: str
    status: JobStatus = "queued"
    progress: float = 0.0
    result: MixResult | IndexReport | None = None
    error: str | None = None


class JobRegistry:
    """Runs jobs one at a time on a worker thread and remembers their state."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="crate-job")

    def submit(self, kind: JobKind, label: str, work: Work) -> Job:
        """Queue ``work`` and return its job immediately."""
        job = Job(job_id=uuid.uuid4().hex[:8], kind=kind, label=label)
        with self._lock:
            self._jobs[job.job_id] = job
        self._executor.submit(self._run, job, work)
        return job

    def get(self, job_id: str) -> Job | None:
        """Look up a job by id."""
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job: Job, work: Work) -> None:
        job.status = "running"

        def progress(fraction: float) -> None:
            job.progress = max(0.0, min(1.0, fraction))

        try:
            job.result = work(progress)
        except Exception as exc:
            logger.exception("Job %s failed", job.job_id)
            job.error = str(exc)
            job.status = "failed"
        else:
            job.progress = 1.0
            job.status = "done"


_registry = JobRegistry()


def get_job_registry() -> JobRegistry:
    """The process-wide job registry."""
    return _registry
