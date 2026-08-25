"""Tests for scripts/run_rfdiffusion.py override building and failure logging."""

from __future__ import annotations

import subprocess

import scripts.run_rfdiffusion as rfdiffusion


def _patch_runner(monkeypatch, tmp_path):
    """Isolate run_rfdiffusion from the environment and capture the tool argv."""
    monkeypatch.setattr(rfdiffusion, "find_rfdiffusion", lambda config: "/fake/rfdiffusion.py")
    monkeypatch.setattr(rfdiffusion, "get_config", lambda tool: {"output_dir": str(tmp_path)})
    monkeypatch.setattr(rfdiffusion, "log_history", lambda *a, **k: None)
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = [str(c) for c in cmd]

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr(rfdiffusion.subprocess, "run", fake_run)
    return calls


def test_hotspot_list_generates_separate_elements(monkeypatch, tmp_path):
    """Each hotspot must become its own quoted list element.

    Upstream RFdiffusion parses every ``ppi.hotspot_res`` item as
    <chain><resnum>, so a merged "A30,A33" item raises ValueError.
    """
    calls = _patch_runner(monkeypatch, tmp_path)

    rc = rfdiffusion.run_rfdiffusion(
        contig="[B1-100/0 100-100]",
        hotspot_res=["A30", "A33"],
        output_prefix="design",
    )

    assert rc == 0
    assert 'ppi.hotspot_res=["A30","A33"]' in calls["cmd"]
    assert 'ppi.hotspot_res=["A30,A33"]' not in calls["cmd"]


def test_hotspot_string_remains_supported(monkeypatch, tmp_path):
    """A comma-separated hotspot string still works and splits per item."""
    calls = _patch_runner(monkeypatch, tmp_path)

    rc = rfdiffusion.run_rfdiffusion(
        contig="100-100",
        hotspot_res="A30,A33",
        output_prefix="design",
    )

    assert rc == 0
    assert 'ppi.hotspot_res=["A30","A33"]' in calls["cmd"]


def test_single_hotspot_keeps_one_element(monkeypatch, tmp_path):
    calls = _patch_runner(monkeypatch, tmp_path)

    rc = rfdiffusion.run_rfdiffusion(
        contig="100-100",
        hotspot_res=["A30"],
        output_prefix="design",
    )

    assert rc == 0
    assert 'ppi.hotspot_res=["A30"]' in calls["cmd"]


def test_timeout_branch_logs_num_designs(monkeypatch, tmp_path):
    """The timeout branch records the same params as the success branch."""
    monkeypatch.setattr(rfdiffusion, "find_rfdiffusion", lambda config: "/fake/rfdiffusion.py")
    monkeypatch.setattr(rfdiffusion, "get_config", lambda tool: {"output_dir": str(tmp_path)})
    logged = []
    monkeypatch.setattr(
        rfdiffusion, "log_history",
        lambda tool, params, runtime, success, output_dir: logged.append(params),
    )

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 3600)

    monkeypatch.setattr(rfdiffusion.subprocess, "run", fake_run)

    rc = rfdiffusion.run_rfdiffusion(contig="100-100", num_designs=7, output_prefix="design")

    assert rc == 3
    assert logged == [{"contig": "100-100", "num_designs": 7}]


def test_generic_exception_branch_logs_num_designs(monkeypatch, tmp_path):
    """The generic-exception branch records the same params as success."""
    monkeypatch.setattr(rfdiffusion, "find_rfdiffusion", lambda config: "/fake/rfdiffusion.py")
    monkeypatch.setattr(rfdiffusion, "get_config", lambda tool: {"output_dir": str(tmp_path)})
    logged = []
    monkeypatch.setattr(
        rfdiffusion, "log_history",
        lambda tool, params, runtime, success, output_dir: logged.append(params),
    )

    def fake_run(cmd, **kwargs):
        raise OSError("spawn failed")

    monkeypatch.setattr(rfdiffusion.subprocess, "run", fake_run)

    rc = rfdiffusion.run_rfdiffusion(contig="100-100", num_designs=7, output_prefix="design")

    assert rc == 3
    assert logged == [{"contig": "100-100", "num_designs": 7}]
