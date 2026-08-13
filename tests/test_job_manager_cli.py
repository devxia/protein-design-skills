"""End-to-end CLI tests for scripts/job_manager.py (#18)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "job_manager.py"


def _run(args: list[str], home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_submit_list_status_roundtrip(tmp_path):
    """The documented `submit -- <cmd>` flow must dispatch, not print usage."""
    home = tmp_path / "home"
    home.mkdir()

    submit = _run(
        ["submit", "--name", "e2e", "--", sys.executable, "-c", "import sys; sys.exit(3)"],
        home,
    )
    assert submit.returncode == 0, f"stdout={submit.stdout!r} stderr={submit.stderr!r}"
    job_id = submit.stdout.strip().splitlines()[-1]
    assert job_id and "usage" not in submit.stdout.lower()

    # Wait for the launcher to record the real exit code.
    exit_file = home / ".protein-design" / "jobs" / f"{job_id}.exit"
    deadline = time.time() + 30
    while time.time() < deadline and not exit_file.exists():
        time.sleep(0.2)
    assert exit_file.exists(), "job did not record an exit code in time"

    status = _run(["status", job_id], home)
    assert status.returncode == 0
    info = json.loads(status.stdout)
    assert info["status"] == "completed"
    assert info["exit_code"] == 3

    listing = _run(["list"], home)
    assert listing.returncode == 0
    assert job_id in listing.stdout


def test_submit_without_command_is_a_clean_error(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = _run(["submit"], home)
    assert result.returncode == 2
    assert "No command specified" in result.stderr
