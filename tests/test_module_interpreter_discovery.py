"""Regression tests for module discovery interpreter consistency."""

from __future__ import annotations

import pytest

import scripts.run_esm_if1 as esm_if1
import scripts.run_ligandmpnn as ligandmpnn
import scripts.run_omegafold as omegafold
import scripts.run_protenix as protenix


class _Result:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def test_omegafold_discovery_preserves_spaced_sys_executable(monkeypatch) -> None:
    python_executable = "/opt/Python Environments/omegafold/bin/python3.11"
    expected_probe = [python_executable, "-m", "omegafold", "--help"]
    monkeypatch.setattr(omegafold.sys, "executable", python_executable)
    monkeypatch.setattr(omegafold.shutil, "which", lambda name: None)
    monkeypatch.setattr(omegafold, "probe_conda_envs", lambda *args, **kwargs: None)

    def fake_run(cmd, **kwargs):
        return _Result(0 if [str(token) for token in cmd] == expected_probe else 1)

    monkeypatch.setattr(omegafold.subprocess, "run", fake_run)

    discovered = omegafold.find_omegafold({})
    assert discovered == omegafold.shlex.join(expected_probe[:-1])
    assert omegafold.build_tool_command(discovered) == expected_probe[:-1]


def test_protenix_discovery_preserves_spaced_sys_executable(monkeypatch) -> None:
    python_executable = "/opt/Python Environments/protenix/bin/python3.11"
    expected_probe = [python_executable, "-m", "protenix", "--help"]
    monkeypatch.setattr(protenix.sys, "executable", python_executable)
    monkeypatch.setattr(protenix, "get_config", lambda tool=None: {})
    monkeypatch.setattr(protenix.shutil, "which", lambda name: None)
    monkeypatch.setattr(protenix, "probe_conda_envs", lambda *args, **kwargs: None)

    def fake_run(cmd, **kwargs):
        return _Result(0 if [str(token) for token in cmd] == expected_probe else 1)

    monkeypatch.setattr(protenix.subprocess, "run", fake_run)

    discovered = protenix.find_protenix()
    assert discovered == protenix.shlex.join(expected_probe[:-1])
    assert protenix.build_tool_command(discovered) == expected_probe[:-1]


def test_esm_if1_discovery_preserves_spaced_sys_executable(monkeypatch) -> None:
    python_executable = "/opt/Python Environments/esm/bin/python3.11"
    expected_command = [python_executable, "-m", "esm.inverse_folding.cli"]
    monkeypatch.setattr(esm_if1.sys, "executable", python_executable)
    monkeypatch.setattr(esm_if1.Path, "exists", lambda self: False)

    def fake_run(cmd, **kwargs):
        tokens = [str(token) for token in cmd]
        if tokens[0] == python_executable:
            return _Result(0)
        return _Result(1)

    monkeypatch.setattr(esm_if1.subprocess, "run", fake_run)

    discovered = esm_if1.find_esm_if1({})
    assert discovered == esm_if1.shlex.join(expected_command)
    assert esm_if1.build_tool_command(discovered) == expected_command


@pytest.mark.parametrize("module", [esm_if1, ligandmpnn])
def test_runner_docstring_records_execution_error_exit_code(module) -> None:
    assert module.__doc__ is not None
    assert "3 = Execution error" in module.__doc__
