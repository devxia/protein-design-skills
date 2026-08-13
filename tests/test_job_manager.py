"""Tests for scripts/job_manager.py exit-code reporting."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import scripts.job_manager as jm


def _patch_jobs_dir(tmp_path, monkeypatch) -> Path:
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(jm, "get_jobs_dir", lambda: jobs_dir)
    return jobs_dir


def _wait_for_completion(job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    status = {}
    while time.time() < deadline:
        status = jm.get_job_status(job_id)
        if status.get("status") == "completed":
            break
        time.sleep(0.05)
    return status


def test_failed_job_reports_nonzero_exit_code(tmp_path, monkeypatch):
    _patch_jobs_dir(tmp_path, monkeypatch)
    job_id = jm.submit_job([sys.executable, "-c", "import sys; sys.exit(3)"])
    status = _wait_for_completion(job_id)
    assert status.get("status") == "completed"
    assert status.get("exit_code") == 3


def test_successful_job_reports_zero_exit_code(tmp_path, monkeypatch):
    _patch_jobs_dir(tmp_path, monkeypatch)
    job_id = jm.submit_job([sys.executable, "-c", "print('ok')"])
    status = _wait_for_completion(job_id)
    assert status.get("status") == "completed"
    assert status.get("exit_code") == 0


def test_missing_executable_records_exit_127(tmp_path, monkeypatch):
    """A command that cannot launch must still record a truthful exit code (#18)."""
    _patch_jobs_dir(tmp_path, monkeypatch)
    job_id = jm.submit_job(["/nonexistent/binary-xyz-12345"])
    status = _wait_for_completion(job_id)
    assert status["status"] == "completed"
    assert status["exit_code"] == 127


def test_wait_job_timeout_returns_documented_code(tmp_path, monkeypatch):
    """A wait timeout must return the documented code 3, not -1 (-> shell 255) (#37)."""
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    job_id = jm.submit_job([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert jm.wait_job(job_id, timeout=-1) == 3
    finally:
        jm.cancel_job(job_id)


def test_wait_job_unknown_id_returns_not_found(tmp_path, monkeypatch):
    """Waiting on a nonexistent job must return 1 immediately, not loop (#37)."""
    _patch_jobs_dir(tmp_path, monkeypatch)
    assert jm.wait_job("no-such-job", timeout=None) == 1


def test_list_jobs_honors_exit_marker_over_pid_liveness(tmp_path, monkeypatch):
    """A live PID must not mask the authoritative completion marker (#18)."""
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    meta = {
        "job_id": "job1",
        "job_name": "t",
        "command": ["true"],
        "pid": os.getpid(),  # alive, so a PID-only check would say "running"
        "status": "running",
        "start_time": "2025-01-01T00:00:00",
        "log_file": str(jobs_dir / "logs" / "job1.log"),
    }
    (jobs_dir / "job1.json").write_text(json.dumps(meta), encoding="utf-8")
    (jobs_dir / "job1.pid").write_text(str(os.getpid()), encoding="utf-8")
    (jobs_dir / "job1.exit").write_text("5", encoding="utf-8")

    jobs = jm.list_jobs()
    assert jobs[0]["current_status"] == "completed"
    assert jobs[0]["exit_code"] == 5


def test_wait_job_returns_real_exit_code(tmp_path, monkeypatch):
    _patch_jobs_dir(tmp_path, monkeypatch)
    job_id = jm.submit_job([sys.executable, "-c", "import sys; sys.exit(7)"])
    assert jm.wait_job(job_id, timeout=30) == 7
