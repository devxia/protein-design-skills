"""Tests for scripts/job_manager.py exit-code reporting."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

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


def _dead_pid() -> int:
    """A PID that is guaranteed dead: spawned, waited on (reaped), not recycled."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def _write_job_files(jobs_dir: Path, job_id: str, pid: int, status: str) -> None:
    """Create tracking files for a job that is not a live child process."""
    meta = {
        "job_id": job_id,
        "job_name": "t",
        "command": ["true"],
        "pid": pid,
        "status": status,
        "start_time": "2025-01-01T00:00:00",
        "log_file": str(jobs_dir / "logs" / f"{job_id}.log"),
    }
    (jobs_dir / f"{job_id}.json").write_text(json.dumps(meta), encoding="utf-8")
    (jobs_dir / f"{job_id}.pid").write_text(str(pid), encoding="utf-8")


def test_cancelled_job_keeps_status_when_pid_dead(tmp_path, monkeypatch):
    """A cancelled job must keep its terminal status; a dead PID must not
    rewrite it to "completed" (which wait would then report as success)."""
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", _dead_pid(), status="cancelled")

    status = jm.get_job_status("job1")
    assert status["status"] == "cancelled"
    assert "exit_code" not in status


def test_wait_job_cancelled_returns_143(tmp_path, monkeypatch):
    """Waiting on a cancelled job must fail with 143 (128 + SIGTERM), not 0."""
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", _dead_pid(), status="cancelled")

    assert jm.wait_job("job1", timeout=5) == 143


def test_dead_job_without_exit_marker_is_failed(tmp_path, monkeypatch):
    """A process that died without writing its exit marker must not be
    reported as a successful completion."""
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", _dead_pid(), status="running")

    status = jm.get_job_status("job1")
    assert status["status"] == "failed"


def test_wait_job_dead_without_marker_returns_nonzero(tmp_path, monkeypatch):
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", _dead_pid(), status="running")

    assert jm.wait_job("job1", timeout=5) != 0


def test_list_jobs_reports_cancelled_not_completed(tmp_path, monkeypatch):
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", _dead_pid(), status="cancelled")

    jobs = jm.list_jobs()
    assert jobs[0]["current_status"] == "cancelled"


def test_cancelled_running_job_waits_nonzero(tmp_path, monkeypatch):
    """End to end: cancel a live job, then wait must not report success."""
    _patch_jobs_dir(tmp_path, monkeypatch)
    job_id = jm.submit_job([sys.executable, "-c", "import time; time.sleep(60)"])
    assert jm.cancel_job(job_id) is True
    assert jm.wait_job(job_id, timeout=10) == 143


@pytest.mark.parametrize("marker", ["", "not-an-integer", "7 trailing", "1_0"])
def test_invalid_exit_marker_does_not_complete_status_or_list(
    tmp_path, monkeypatch, marker
):
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", os.getpid(), status="running")
    (jobs_dir / "job1.exit").write_text(marker, encoding="utf-8")

    status = jm.get_job_status("job1")
    jobs = jm.list_jobs()

    assert status["status"] == "running"
    assert "exit_code" not in status
    assert jobs[0]["current_status"] == "running"
    assert "exit_code" not in jobs[0]


def test_launcher_atomically_publishes_final_exit_marker(tmp_path, monkeypatch):
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    job_id = jm.submit_job([sys.executable, "-c", "import sys; sys.exit(9)"])

    status = _wait_for_completion(job_id)

    assert status["exit_code"] == 9
    assert (jobs_dir / f"{job_id}.exit").read_text(encoding="utf-8") == "9"
    assert list(jobs_dir.glob(f"{job_id}.exit.tmp.*")) == []


def test_submit_records_available_process_identity(tmp_path, monkeypatch):
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    identity = {"kind": "test_creation_time", "value": "123"}
    monkeypatch.setattr(jm, "get_process_identity", lambda pid: identity)
    job_id = jm.submit_job([sys.executable, "-c", "import time; time.sleep(60)"])

    metadata = json.loads((jobs_dir / f"{job_id}.json").read_text(encoding="utf-8"))
    try:
        assert metadata["process_identity"] == identity
    finally:
        jm.terminate_process_group(metadata["pid"], force=True)


@pytest.mark.parametrize(
    "current_identity",
    [None, {"kind": "test_creation_time", "value": "reused"}],
)
def test_cancel_fails_safe_when_recorded_identity_cannot_be_confirmed(
    tmp_path, monkeypatch, current_identity
):
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", 1234, status="running")
    meta_file = jobs_dir / "job1.json"
    metadata = json.loads(meta_file.read_text(encoding="utf-8"))
    metadata["process_identity"] = {"kind": "test_creation_time", "value": "original"}
    meta_file.write_text(json.dumps(metadata), encoding="utf-8")
    terminate_calls = []
    monkeypatch.setattr(jm, "get_job_status", lambda job_id: {"status": "running"})
    monkeypatch.setattr(jm, "get_process_identity", lambda pid: current_identity)
    monkeypatch.setattr(
        jm, "terminate_process_group", lambda *args, **kwargs: terminate_calls.append(args)
    )

    assert jm.cancel_job("job1") is False
    assert terminate_calls == []
    assert json.loads(meta_file.read_text(encoding="utf-8"))["status"] == "running"


def test_cancel_does_not_report_success_when_no_signal_was_sent(tmp_path, monkeypatch):
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", 1234, status="running")
    meta_file = jobs_dir / "job1.json"
    monkeypatch.setattr(jm, "get_job_status", lambda job_id: {"status": "running"})
    monkeypatch.setattr(jm, "terminate_process_group", lambda pid, force=False: False)

    assert jm.cancel_job("job1") is False
    assert json.loads(meta_file.read_text(encoding="utf-8"))["status"] == "running"


def test_cancel_does_not_publish_cancelled_while_group_survives(tmp_path, monkeypatch):
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", 1234, status="running")
    meta_file = jobs_dir / "job1.json"
    terminate_calls = []
    monkeypatch.setattr(jm, "get_job_status", lambda job_id: {"status": "running"})
    monkeypatch.setattr(
        jm,
        "terminate_process_group",
        lambda pid, force=False: terminate_calls.append(force) or True,
    )
    monkeypatch.setattr(
        jm,
        "_wait_for_process_group_exit",
        lambda pid, timeout, **kwargs: False,
    )

    assert jm.cancel_job("job1") is False
    assert terminate_calls == [False, True]
    assert json.loads(meta_file.read_text(encoding="utf-8"))["status"] == "running"


def test_cancel_accepts_exit_race_after_successful_graceful_signal(tmp_path, monkeypatch):
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", 1234, status="running")
    meta_file = jobs_dir / "job1.json"
    terminate_results = iter([True, False])
    monkeypatch.setattr(jm, "get_job_status", lambda job_id: {"status": "running"})
    monkeypatch.setattr(
        jm,
        "terminate_process_group",
        lambda pid, force=False: next(terminate_results),
    )
    monkeypatch.setattr(
        jm,
        "_wait_for_process_group_exit",
        lambda pid, timeout, **kwargs: False,
    )
    monkeypatch.setattr(jm, "process_group_is_alive", lambda pid, **kwargs: False)

    assert jm.cancel_job("job1") is True
    assert json.loads(meta_file.read_text(encoding="utf-8"))["status"] == "cancelled"


def test_cancel_old_metadata_after_confirmed_group_exit(tmp_path, monkeypatch):
    """Metadata without process identity remains backward compatible."""
    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    _write_job_files(jobs_dir, "job1", 1234, status="running")
    meta_file = jobs_dir / "job1.json"
    monkeypatch.setattr(jm, "get_job_status", lambda job_id: {"status": "running"})
    monkeypatch.setattr(jm, "get_process_identity", lambda pid: pytest.fail("not expected"))
    monkeypatch.setattr(jm, "terminate_process_group", lambda pid, force=False: True)
    monkeypatch.setattr(
        jm,
        "_wait_for_process_group_exit",
        lambda pid, timeout, **kwargs: True,
    )

    assert jm.cancel_job("job1") is True
    assert json.loads(meta_file.read_text(encoding="utf-8"))["status"] == "cancelled"


def test_wait_job_timeout_zero_is_immediate_and_monotonic(monkeypatch):
    monotonic_calls = []

    def monotonic():
        monotonic_calls.append(None)
        return 10.0

    monkeypatch.setattr(jm, "get_job_status", lambda job_id: {"status": "running"})
    monkeypatch.setattr(jm.time, "monotonic", monotonic)
    monkeypatch.setattr(jm.time, "sleep", lambda seconds: pytest.fail("must not sleep"))

    assert jm.wait_job("job1", timeout=0) == 3
    assert len(monotonic_calls) == 2


def test_cli_rejects_negative_wait_timeout(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["job_manager.py", "wait", "job1", "--timeout", "-1"])

    with pytest.raises(SystemExit) as exc_info:
        jm.main()

    assert exc_info.value.code == 2


@pytest.mark.skipif(os.name != "posix", reason="uses POSIX process groups")
def test_cancel_reaches_tool_through_batch_runner_and_nested_runner(
    tmp_path, monkeypatch
):
    """One outer group must own job_manager -> batch -> runner -> tool."""
    from protein_design import process_utils

    jobs_dir = _patch_jobs_dir(tmp_path, monkeypatch)
    tool_pid_file = tmp_path / "tool.pid"
    config_file = tmp_path / "pipeline.json"
    batch_runner = Path(jm.__file__).with_name("batch_runner.py")
    tool_code = (
        "import os, pathlib, sys, time\n"
        "pathlib.Path(sys.argv[1]).write_text(f'{os.getpid()} {os.getpgrp()}')\n"
        "time.sleep(60)\n"
    )
    runner_code = (
        "import sys\n"
        "from protein_design.process_utils import run_process\n"
        "result = run_process([sys.executable, '-c', sys.argv[2], sys.argv[1]])\n"
        "raise SystemExit(result.returncode)\n"
    )
    config_file.write_text(
        json.dumps(
            {
                "stages": [
                    {
                        "name": "nested runner",
                        "command": [
                            sys.executable,
                            "-c",
                            runner_code,
                            str(tool_pid_file),
                            tool_code,
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    job_id = None
    owner_pid = None
    tool_pid = None
    tool_pgid = None
    try:
        job_id = jm.submit_job(
            [sys.executable, str(batch_runner), "--config", str(config_file)]
        )
        metadata = json.loads(
            (jobs_dir / f"{job_id}.json").read_text(encoding="utf-8")
        )
        owner_pid = metadata["pid"]

        deadline = time.monotonic() + 10
        while not tool_pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert tool_pid_file.exists(), jm.tail_log(job_id, lines=100)
        tool_pid, tool_pgid = map(
            int, tool_pid_file.read_text(encoding="utf-8").split()
        )
        assert tool_pgid == owner_pid, "the real tool escaped the job-owned group"

        assert jm.cancel_job(job_id) is True
        deadline = time.monotonic() + 5
        while (
            process_utils.process_is_alive(tool_pid) is not False
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)
        assert process_utils.process_is_alive(tool_pid) is False
    finally:
        if job_id is not None and jm.get_job_status(job_id).get("status") == "running":
            jm.cancel_job(job_id)
        if owner_pid is not None:
            process_utils.terminate_process_group(owner_pid, force=True)
        if tool_pgid is not None and tool_pgid != os.getpgrp():
            try:
                os.killpg(tool_pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        if tool_pid is not None:
            try:
                os.kill(tool_pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
