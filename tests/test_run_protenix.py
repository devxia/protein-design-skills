"""Tests for scripts/run_protenix.py CLI form detection and input validation."""

from __future__ import annotations

import json
import subprocess
import sys

import scripts.run_protenix as protenix


class _FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _mock_environment(monkeypatch, tmp_path, found="protenix"):
    """Hermetically mock config/discovery/history for a Protenix run."""
    monkeypatch.setattr(protenix, "get_config", lambda tool=None: {"output_dir": str(tmp_path)})
    monkeypatch.setattr(protenix, "find_protenix", lambda: found)
    monkeypatch.setattr(protenix, "log_history", lambda *a, **k: None)


def _install_fake_subprocess(monkeypatch, probe_rcs):
    """Patch subprocess.run; ``probe_rcs`` maps subcommand → ``--help`` exit code."""
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = [str(c) for c in cmd]
        calls.append(cmd)
        if "--help" in cmd:
            return _FakeResult(probe_rcs.get(cmd[-2], 1))
        return _FakeResult()

    monkeypatch.setattr(protenix.subprocess, "run", fake_run)
    return calls


def test_uses_predict_form_with_long_flags(tmp_path, monkeypatch):
    """Protenix v0.5.x form: ``protenix predict --input <json> --out_dir <dir>``."""
    input_json = tmp_path / "input.json"
    input_json.write_text("{}", encoding="utf-8")
    out_dir = tmp_path / "out"
    _mock_environment(monkeypatch, tmp_path)
    calls = _install_fake_subprocess(monkeypatch, {"predict": 0, "pred": 0})

    rc = protenix.run_protenix(str(input_json), str(out_dir))

    assert rc == 0
    exec_cmd = calls[-1]
    assert exec_cmd[:3] == ["protenix", "predict", "--input"]
    assert str(input_json) in exec_cmd
    assert "--out_dir" in exec_cmd
    assert str(out_dir) in exec_cmd
    # Default recycling value (3) is not forwarded explicitly.
    assert "--cycle" not in exec_cmd
    assert "--num_recycling" not in exec_cmd


def test_falls_back_to_pred_form_when_predict_missing(tmp_path, monkeypatch):
    """Newer CLI: ``protenix pred -i <json> -o <dir>``; --num-recycling maps to --cycle."""
    input_json = tmp_path / "input.json"
    input_json.write_text("{}", encoding="utf-8")
    out_dir = tmp_path / "out"
    _mock_environment(monkeypatch, tmp_path)
    calls = _install_fake_subprocess(monkeypatch, {"predict": 1, "pred": 0})

    rc = protenix.run_protenix(str(input_json), str(out_dir), num_recycling=5)

    assert rc == 0
    exec_cmd = calls[-1]
    assert exec_cmd[:3] == ["protenix", "pred", "-i"]
    assert "-o" in exec_cmd
    cycle_idx = exec_cmd.index("--cycle")
    assert exec_cmd[cycle_idx + 1] == "5"
    assert "--num_recycling" not in exec_cmd


def test_probe_timeout_falls_back_to_predict_form(tmp_path, monkeypatch):
    """Probe timeouts must not crash; the v0.5.x form is used as fallback."""
    input_json = tmp_path / "input.json"
    input_json.write_text("{}", encoding="utf-8")
    out_dir = tmp_path / "out"
    _mock_environment(monkeypatch, tmp_path)

    def fake_run(cmd, **kwargs):
        if "--help" in [str(c) for c in cmd]:
            raise subprocess.TimeoutExpired(cmd, 30)
        return _FakeResult()

    monkeypatch.setattr(protenix.subprocess, "run", fake_run)

    rc = protenix.run_protenix(str(input_json), str(out_dir))

    assert rc == 0


def test_main_missing_input_exits_1_before_discovery(tmp_path, monkeypatch, capsys):
    """A missing input file must exit 1 before tool discovery or FASTA conversion."""
    missing = tmp_path / "missing.fa"
    out_dir = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "run_protenix.py", "--input", str(missing),
        "--output-dir", str(out_dir), "--from-fasta",
    ])
    discovery_calls = []

    def fake_find():
        discovery_calls.append(1)
        return "protenix"

    monkeypatch.setattr(protenix, "find_protenix", fake_find)

    rc = protenix.main()

    assert rc == 1
    assert discovery_calls == []
    assert not (out_dir / "protenix_input.json").exists()
    assert "not found" in capsys.readouterr().err


def test_from_fasta_waits_for_tool_confirmation(tmp_path, monkeypatch):
    """--from-fasta must not write protenix_input.json when Protenix is missing."""
    fasta = tmp_path / "in.fa"
    fasta.write_text(">seq1\nACDEFG\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    _mock_environment(monkeypatch, tmp_path, found=None)

    rc = protenix.run_protenix(str(fasta), str(out_dir), from_fasta=True)

    assert rc == 2
    assert not out_dir.exists()


def test_from_fasta_converts_and_runs_json(tmp_path, monkeypatch):
    """--from-fasta converts after tool confirmation and passes the JSON upstream."""
    fasta = tmp_path / "in.fa"
    fasta.write_text(">seq1\nACDEFG\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    _mock_environment(monkeypatch, tmp_path)
    calls = _install_fake_subprocess(monkeypatch, {"predict": 0})

    rc = protenix.run_protenix(str(fasta), str(out_dir), from_fasta=True, verbose=True)

    assert rc == 0
    json_file = out_dir / "protenix_input.json"
    assert json_file.exists()
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data["sequences"][0]["protein"]["sequence"] == "ACDEFG"
    exec_cmd = calls[-1]
    # The generated JSON — not the FASTA — is passed to Protenix.
    assert str(json_file) in exec_cmd
    assert str(fasta) not in exec_cmd
