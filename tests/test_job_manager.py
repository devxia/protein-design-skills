"""Tests for scripts/job_manager.py exit-code reporting."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def test_wait_job_returns_real_exit_code(tmp_path, monkeypatch):
    _patch_jobs_dir(tmp_path, monkeypatch)
    job_id = jm.submit_job([sys.executable, "-c", "import sys; sys.exit(7)"])
    assert jm.wait_job(job_id, timeout=30) == 7
