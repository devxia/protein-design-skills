"""Tests for process-group isolation and tree termination."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

import protein_design.process_utils as process_utils


def _pid_is_alive(pid: int) -> bool:
    """Treat zombies as dead while conservatively handling an unknown result."""
    return process_utils.process_is_alive(pid) is not False


def _wait_for_pid_exit(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_is_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_is_alive(pid)


def _force_cleanup_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _ignoring_child_code() -> str:
    return (
        "import os, pathlib, signal, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "pathlib.Path(sys.argv[1]).write_text(f'{os.getpid()} {os.getpgrp()}')\n"
        "time.sleep(60)\n"
    )


def _leader_with_ignoring_child_code() -> str:
    return (
        "import pathlib, subprocess, sys, time\n"
        "pid_file = pathlib.Path(sys.argv[1])\n"
        "subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "deadline = time.monotonic() + 5\n"
        "while not pid_file.exists() and time.monotonic() < deadline: time.sleep(0.01)\n"
        "time.sleep(60)\n"
    )


@pytest.mark.skipif(os.name != "posix", reason="uses POSIX process groups")
def test_run_process_timeout_terminates_descendants(tmp_path: Path) -> None:
    """A timeout must terminate the command and its separately spawned child."""
    child_pid_file = tmp_path / "child.pid"
    child_pid = None
    command = [
        sys.executable,
        "-c",
        (
            "import pathlib, subprocess, sys, time\n"
            "pid_file = pathlib.Path(sys.argv[1])\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "pid_file.write_text(str(child.pid))\n"
            "child.wait()\n"
        ),
        str(child_pid_file),
    ]

    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process_utils.run_process(command, timeout=0.2)

        assert child_pid_file.exists(), "parent did not record its child PID"
        child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        assert _wait_for_pid_exit(child_pid), f"descendant {child_pid} survived timeout"
    finally:
        if child_pid is None and child_pid_file.exists():
            child_pid = int(child_pid_file.read_text(encoding="utf-8").split()[0])
        if child_pid is not None:
            _force_cleanup_pid(child_pid)


@pytest.mark.skipif(os.name != "posix", reason="uses POSIX process groups")
def test_timeout_force_kills_group_after_leader_exits(tmp_path: Path) -> None:
    """An ignore-SIGTERM child must be killed after its group leader exits."""
    child_pid_file = tmp_path / "ignoring-child.pid"
    child_pid = None
    child_pgid = None
    command = [
        sys.executable,
        "-c",
        _leader_with_ignoring_child_code(),
        str(child_pid_file),
        _ignoring_child_code(),
    ]

    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process_utils.run_process(command, timeout=0.3)

        child_pid, child_pgid = map(
            int, child_pid_file.read_text(encoding="utf-8").split()
        )
        assert child_pgid != os.getpgrp(), "direct runner did not isolate its tree"
        assert _wait_for_pid_exit(child_pid), (
            f"ignore-SIGTERM descendant {child_pid} survived timeout"
        )
    finally:
        if child_pid is None and child_pid_file.exists():
            child_pid, child_pgid = map(
                int, child_pid_file.read_text(encoding="utf-8").split()
            )
        if child_pgid is not None and child_pgid != os.getpgrp():
            try:
                os.killpg(child_pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        if child_pid is not None:
            _force_cleanup_pid(child_pid)


@pytest.mark.skipif(os.name != "posix", reason="uses POSIX process groups")
def test_nested_timeout_kills_descendants_without_killing_caller(tmp_path: Path) -> None:
    """A nested runner inherits its group and times out only its own subtree."""
    child_pid_file = tmp_path / "nested-child.pid"
    caller_result_file = tmp_path / "caller-survived.txt"
    child_pid = None
    outer = None
    outer_code = (
        "import os, pathlib, subprocess, sys\n"
        "from protein_design.process_utils import run_process\n"
        "try:\n"
        "    run_process([sys.executable, '-c', sys.argv[3], sys.argv[1], sys.argv[4]], timeout=0.3)\n"
        "except subprocess.TimeoutExpired:\n"
        "    pathlib.Path(sys.argv[2]).write_text(f'{os.getpid()} {os.getpgrp()}')\n"
        "else:\n"
        "    raise SystemExit(2)\n"
    )

    try:
        outer = subprocess.Popen(
            [
                sys.executable,
                "-c",
                outer_code,
                str(child_pid_file),
                str(caller_result_file),
                _leader_with_ignoring_child_code(),
                _ignoring_child_code(),
            ],
            cwd=str(Path(process_utils.__file__).resolve().parents[1]),
            **process_utils.process_group_popen_kwargs(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ),
        )
        stdout, stderr = outer.communicate(timeout=15)
        assert outer.returncode == 0, (stdout, stderr)
        assert caller_result_file.exists(), "nested timeout killed its caller"

        caller_pid, caller_pgid = map(
            int, caller_result_file.read_text(encoding="utf-8").split()
        )
        child_pid, child_pgid = map(
            int, child_pid_file.read_text(encoding="utf-8").split()
        )
        assert caller_pid == outer.pid
        assert caller_pgid == outer.pid
        assert child_pgid == outer.pid, "nested run_process created an escaping group"
        assert _wait_for_pid_exit(child_pid), f"nested descendant {child_pid} survived"
    finally:
        if outer is not None:
            process_utils.terminate_process_group(outer.pid, force=True)
            if outer.poll() is None:
                outer.kill()
                outer.wait(timeout=5)
        if child_pid is None and child_pid_file.exists():
            child_pid = int(child_pid_file.read_text(encoding="utf-8").split()[0])
        if child_pid is not None:
            _force_cleanup_pid(child_pid)


@pytest.mark.skipif(os.name != "posix", reason="tests POSIX signal fallback")
def test_terminate_process_group_falls_back_to_leader(monkeypatch) -> None:
    """An unavailable process group must fall back to signalling the leader."""
    calls = []

    def missing_group(*args):
        raise ProcessLookupError

    monkeypatch.setattr(process_utils.os, "killpg", missing_group)
    monkeypatch.setattr(process_utils.os, "kill", lambda *args: calls.append(args))

    assert process_utils.terminate_process_group(1234) is True
    assert calls == [(1234, signal.SIGTERM)]


@pytest.mark.skipif(os.name != "posix", reason="tests POSIX signal result")
def test_terminate_process_group_reports_permission_failure(monkeypatch) -> None:
    """A denied group signal must propagate as a false result."""

    def denied(*args):
        raise PermissionError

    monkeypatch.setattr(process_utils.os, "killpg", denied)
    assert process_utils.terminate_process_group(1234) is False


@pytest.mark.skipif(os.name != "posix", reason="tests POSIX group probing")
def test_process_group_is_alive_falls_back_to_leader(monkeypatch) -> None:
    """Older, non-isolated jobs are probed through their leader PID."""

    def missing_group(*args):
        raise ProcessLookupError

    monkeypatch.setattr(process_utils.os, "killpg", missing_group)
    monkeypatch.setattr(process_utils, "process_is_alive", lambda pid: False)
    assert process_utils.process_group_is_alive(1234) is False


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [("1234 Z\n1234 Z+\n999 S\n", False), ("1234 Z\n1234 S+\n", True)],
)
def test_posix_group_liveness_ignores_zombie_members(monkeypatch, stdout, expected):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(process_utils, "_ORIGINAL_SUBPROCESS_RUN", fake_run)

    assert process_utils._posix_ps_liveness(1234, group=True) is expected


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="uses Linux /proc identity")
def test_get_process_identity_is_stable_for_current_process() -> None:
    first = process_utils.get_process_identity(os.getpid())
    second = process_utils.get_process_identity(os.getpid())

    assert first is not None
    assert first["kind"] == "linux_proc_start_ticks"
    assert first == second


def test_get_process_identity_dispatches_to_windows(monkeypatch) -> None:
    expected = {"kind": "windows_creation_filetime", "value": "123"}
    monkeypatch.setattr(process_utils.os, "name", "nt")
    monkeypatch.setattr(process_utils, "_windows_process_identity", lambda pid: expected)

    assert process_utils.get_process_identity(42) == expected


def test_process_group_popen_kwargs_windows(monkeypatch) -> None:
    """Windows uses a new process group creation flag."""
    monkeypatch.setattr(process_utils.os, "name", "nt")
    monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)

    kwargs = process_utils.process_group_popen_kwargs()

    assert kwargs["creationflags"] & 0x200
    assert "start_new_session" not in kwargs


def test_terminate_process_group_windows_uses_taskkill(monkeypatch) -> None:
    """Windows cancellation must request recursive task termination."""
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(process_utils.os, "name", "nt")
    monkeypatch.setattr(process_utils, "_ORIGINAL_SUBPROCESS_RUN", fake_run)

    assert process_utils.terminate_process_group(4321, force=True) is True
    assert commands == [
        (
            ["taskkill", "/PID", "4321", "/T", "/F"],
            {"capture_output": True, "text": True, "timeout": 10, "check": False},
        )
    ]


def test_terminate_process_group_windows_propagates_taskkill_failure(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(process_utils.os, "name", "nt")
    monkeypatch.setattr(process_utils, "_ORIGINAL_SUBPROCESS_RUN", fake_run)

    assert process_utils.terminate_process_group(4321) is False
