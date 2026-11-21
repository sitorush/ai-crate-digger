"""Tests for the background job registry."""

import time

import pytest

from ai_crate_digger.fingerprint.jobs import Job, JobRegistry, ProgressFn
from ai_crate_digger.fingerprint.matcher import MixResult


def _wait(registry: JobRegistry, job_id: str) -> Job:
    deadline = time.time() + 10
    while time.time() < deadline:
        job = registry.get(job_id)
        assert job is not None
        if job.status in ("done", "failed"):
            return job
        time.sleep(0.01)
    pytest.fail("job did not finish")


def test_successful_job_stores_result_and_full_progress() -> None:
    registry = JobRegistry()
    result = MixResult(duration_sec=1.0)

    def work(progress: ProgressFn) -> MixResult:
        progress(0.5)
        return result

    job = registry.submit("mix", "set.mp3", work)
    finished = _wait(registry, job.job_id)
    assert finished.status == "done"
    assert finished.result is result
    assert finished.progress == 1.0
    assert finished.label == "set.mp3"


def test_failing_job_records_the_error() -> None:
    registry = JobRegistry()

    def work(progress: ProgressFn) -> MixResult:
        msg = "boom"
        raise RuntimeError(msg)

    finished = _wait(registry, registry.submit("index", "library", work).job_id)
    assert finished.status == "failed"
    assert finished.error == "boom"
    assert finished.result is None


def test_progress_is_clamped() -> None:
    registry = JobRegistry()
    reporters: list[ProgressFn] = []

    def work(progress: ProgressFn) -> MixResult:
        reporters.append(progress)
        return MixResult(duration_sec=0.0)

    job = _wait(registry, registry.submit("mix", "x", work).job_id)
    reporters[0](7.0)
    assert job.progress == 1.0
    reporters[0](-3.0)
    assert job.progress == 0.0


def test_unknown_job_is_none() -> None:
    assert JobRegistry().get("nope") is None
