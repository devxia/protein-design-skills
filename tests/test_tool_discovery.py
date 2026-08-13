"""Tests: tool discovery must not scan the user's home directory (#24)."""

from __future__ import annotations

import scripts.run_esm_if1 as esm_if1
import scripts.run_ligandmpnn as ligandmpnn
import scripts.run_rfdiffusion as rfdiffusion


def _no_files_exist(module, monkeypatch):
    """Force every filesystem existence check to fail (hermetic discovery)."""
    monkeypatch.setattr(module.Path, "exists", lambda self: False)


def _assert_no_home_find(calls):
    """No probe may shell out to `find` (the old home-wide scan)."""
    for cmd in calls:
        assert "find" not in cmd, f"home-wide find still used: {cmd}"


def test_rfdiffusion_discovery_uses_targeted_probe(monkeypatch):
    _no_files_exist(rfdiffusion, monkeypatch)
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = [str(c) for c in cmd]
        calls.append(cmd)
        joined = " ".join(cmd)

        class R:
            def __init__(self, returncode=1, stdout=""):
                self.returncode = returncode
                self.stdout = stdout

        if "print(rfdiffusion.__file__)" in joined:
            return R(0, "/env/RFdiffusion/rfdiffusion/__init__.py\n")
        if "run_inference.py" in joined and "pathlib" in joined:
            return R(0, "/env/RFdiffusion/scripts/run_inference.py\n")
        return R()

    monkeypatch.setattr(rfdiffusion.subprocess, "run", fake_run)
    result = rfdiffusion.find_rfdiffusion({})
    assert result == "/env/RFdiffusion/scripts/run_inference.py"
    _assert_no_home_find(calls)


def test_esm_if1_discovery_uses_repo_relative_probe(monkeypatch):
    _no_files_exist(esm_if1, monkeypatch)
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = [str(c) for c in cmd]
        calls.append(cmd)
        joined = " ".join(cmd)

        class R:
            def __init__(self, returncode=1, stdout=""):
                self.returncode = returncode
                self.stdout = stdout

        if "sample_sequences.py" in joined and "pathlib" in joined:
            return R(0, "/env/esm-repo/examples/inverse_folding/sample_sequences.py\n")
        return R()

    monkeypatch.setattr(esm_if1.subprocess, "run", fake_run)
    result = esm_if1.find_esm_if1({})
    assert result == "conda run -n esm_if1 python /env/esm-repo/examples/inverse_folding/sample_sequences.py"
    _assert_no_home_find(calls)


def test_ligandmpnn_discovery_uses_site_packages_probe(monkeypatch):
    _no_files_exist(ligandmpnn, monkeypatch)
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = [str(c) for c in cmd]
        calls.append(cmd)
        joined = " ".join(cmd)

        class R:
            def __init__(self, returncode=1, stdout=""):
                self.returncode = returncode
                self.stdout = stdout

        if "LigandMPNN" in joined and "site-packages" in joined.replace("getsitepackages", "site-packages"):
            return R(0, "/env/lib/python3.10/site-packages/LigandMPNN/run.py\n")
        return R()

    monkeypatch.setattr(ligandmpnn.subprocess, "run", fake_run)
    result = ligandmpnn.find_ligandmpnn({})
    assert result == "conda run -n ligandmpnn python /env/lib/python3.10/site-packages/LigandMPNN/run.py"
    _assert_no_home_find(calls)
