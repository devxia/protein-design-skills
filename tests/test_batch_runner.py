"""Tests for scripts/batch_runner.py config loading."""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.batch_runner import load_pipeline_config


def test_load_pipeline_config_malformed_yaml_reports_error(tmp_path, capsys):
    """Malformed YAML must produce a readable error, never a traceback (#23)."""
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("stages: [unclosed\n  bad indent: :\n", encoding="utf-8")
    stages = load_pipeline_config(cfg)
    assert stages == []
    assert "ERROR" in capsys.readouterr().err


def test_load_pipeline_config_malformed_json_fallback(tmp_path, monkeypatch, capsys):
    """Without pyyaml, a malformed JSON fallback must also be a readable error (#23)."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("No module named 'yaml'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    cfg = tmp_path / "bad.json"
    cfg.write_text("{not valid json", encoding="utf-8")
    stages = load_pipeline_config(cfg)
    assert stages == []
    assert "ERROR" in capsys.readouterr().err


def test_load_pipeline_config_non_dict_config(tmp_path, capsys):
    """A syntactically valid but non-mapping config is invalid, not a crash (#23)."""
    cfg = tmp_path / "list.yaml"
    cfg.write_text("- just\n- a\n- list\n", encoding="utf-8")
    stages = load_pipeline_config(cfg)
    assert stages == []
    assert "ERROR" in capsys.readouterr().err


def test_load_pipeline_config_resolves_script_tokens_anywhere(tmp_path):
    cfg = tmp_path / "pipeline.yaml"
    cfg.write_text(
        "stages:\n"
        "  - name: fix\n"
        "    command: [python, scripts/run_pdbfixer.py, --input, a.pdb]\n"
    )
    stages = load_pipeline_config(cfg)
    assert stages, "expected at least one stage"
    cmd = stages[0]["command"]
    # A bare "python" launcher is rewritten to the current interpreter.
    assert cmd[0] == sys.executable
    assert Path(cmd[1]).is_absolute()
    assert cmd[1].endswith("run_pdbfixer.py")
    # Non-script tokens are left untouched.
    assert cmd[2:] == ["--input", "a.pdb"]


def test_load_pipeline_config_leaves_non_script_tokens(tmp_path):
    cfg = tmp_path / "pipeline.yaml"
    cfg.write_text(
        "stages:\n"
        "  - name: stage\n"
        "    command: [echo, hello]\n"
    )
    stages = load_pipeline_config(cfg)
    assert stages[0]["command"] == ["echo", "hello"]


def test_build_standard_pipeline_uses_current_interpreter(tmp_path):
    """Every built stage command must launch with sys.executable, not PATH's python."""
    from types import SimpleNamespace

    from scripts.batch_runner import build_standard_pipeline

    args = SimpleNamespace(
        input_pdb=None,
        stage=0,
        contig="150-150",
        num_designs=5,
        num_seq=4,
        validator="omegafold",
        output_dir=tmp_path,
        hotspot_res=None,
        min_plddt=75.0,
        top_n=10,
    )
    stages = build_standard_pipeline(args)
    assert len(stages) >= 4
    for stage in stages:
        assert stage["command"][0] == sys.executable, stage["name"]


def test_run_pipeline_stages_missing_command_fails_closed(capsys):
    """A stage without a command is a config error, not a silent skip."""
    from scripts.batch_runner import run_pipeline_stages

    stages = [{"name": "Broken Stage", "cmd": ["echo", "typo-key"]}]
    assert run_pipeline_stages(stages) is False
    err = capsys.readouterr().err
    assert "ERROR" in err
    assert "Broken Stage" in err


def test_main_exit_1_when_stage_has_no_command(tmp_path, monkeypatch, capsys):
    """A misconfigured stage (missing 'command' key) must exit 1, not 0."""
    from scripts.batch_runner import main

    cfg = tmp_path / "pipeline.yaml"
    cfg.write_text(
        "stages:\n"
        "  - name: fix\n"
        "    cmd: [echo, never-runs]\n"
    )
    monkeypatch.setattr(sys, "argv", ["batch_runner.py", "--config", str(cfg)])
    assert main() == 1
    assert "ERROR" in capsys.readouterr().err


def test_concat_fasta_excludes_its_own_output(tmp_path):
    """On re-runs, a previous all_sequences.fa must not re-enter the input."""
    import subprocess

    from scripts.batch_runner import _concat_fasta_command

    seq_dir = tmp_path / "sequences"
    seq_dir.mkdir()
    (seq_dir / "a.fa").write_text(">a\nAAAA\n", encoding="utf-8")
    seqs = (">a\nAAAA\n"
            ">b\nBBBB\n")
    (seq_dir / "b.fasta").write_text(">b\nBBBB\n", encoding="utf-8")
    out = seq_dir / "all_sequences.fa"
    out.write_text(seqs, encoding="utf-8")  # stale output from a previous run

    cmd = _concat_fasta_command(seq_dir, out)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert out.read_text(encoding="utf-8") == seqs
