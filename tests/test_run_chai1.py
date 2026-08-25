"""Tests for scripts/run_chai1.py pip-install probing."""

from __future__ import annotations

import subprocess
import sys

import scripts.run_chai1 as chai1


def test_pip_probe_uses_sys_executable_and_survives_timeout(monkeypatch):
    """The pip probe must run under the current interpreter and treat a probe
    timeout (importing chai_lab pulls in torch) as a failed discovery path,
    not a crash."""
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = [str(c) for c in cmd]
        calls.append(cmd)

        class R:
            def __init__(self):
                self.returncode = 1
                self.stdout = ""
                self.stderr = ""

        if cmd[0] == sys.executable and "chai_lab" in cmd:
            raise subprocess.TimeoutExpired(cmd, 5)
        return R()

    monkeypatch.setattr(chai1.subprocess, "run", fake_run)

    # Every discovery path fails: falls through to None (clean exit 2
    # downstream) instead of raising TimeoutExpired.
    assert chai1.find_chai1({}) is None

    pip_probes = [c for c in calls if c[0] == sys.executable and "chai_lab" in c]
    assert pip_probes, "pip probe should run via sys.executable"
    assert not any(c[0] == "python" for c in calls)


def test_pip_probe_success_returns_module_command(monkeypatch):
    def fake_run(cmd, **kwargs):
        cmd = [str(c) for c in cmd]

        class R:
            def __init__(self, returncode):
                self.returncode = returncode
                self.stdout = ""
                self.stderr = ""

        return R(0 if cmd[0] == sys.executable else 1)

    monkeypatch.setattr(chai1.subprocess, "run", fake_run)
    assert chai1.find_chai1({}) == "python -m chai_lab"
