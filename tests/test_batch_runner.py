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


def _standard_args(tmp_path, **overrides):
    from types import SimpleNamespace

    values = {
        "input_pdb": None,
        "stage": 0,
        "contig": None,
        "num_designs": 5,
        "num_seq": 4,
        "validator": None,
        "output_dir": tmp_path,
        "hotspot_res": None,
        "min_plddt": 75.0,
        "top_n": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_standard_pipeline_passes_fixed_pdb_without_build_time_exists(tmp_path):
    """Stage 1 must reference Stage 0's future output on a first run."""
    from scripts.batch_runner import build_standard_pipeline

    stages = build_standard_pipeline(
        _standard_args(tmp_path, input_pdb=tmp_path / "target.pdb", contig="150-150")
    )
    stage1 = next(stage for stage in stages if stage["name"].startswith("Stage 1:"))
    command = stage1["command"]

    assert command[command.index("--input-pdb") + 1] == str(tmp_path / "fixed.pdb")
    assert "--skip-preprocessing" in command


def test_stage4_is_built_without_validator(tmp_path):
    """Explicit Stage 4 must run filtering even when no validator is selected."""
    from scripts.batch_runner import build_standard_pipeline

    stages = build_standard_pipeline(_standard_args(tmp_path, stage=4))

    assert [stage["name"] for stage in stages] == ["Stage 4: Filtering"]


def test_validation_pipeline_is_candidate_wise_not_a_multi_chain_concat(tmp_path):
    """Validation must split candidates instead of making one multi-chain job."""
    from scripts.batch_runner import build_standard_pipeline

    stages = build_standard_pipeline(
        _standard_args(tmp_path, stage=3, validator="alphafold3")
    )
    names = [stage["name"] for stage in stages]
    commands = [token for stage in stages for token in stage["command"]]

    assert any("Split candidates" in name for name in names)
    assert any("Candidate-wise" in name for name in names)
    assert "all_sequences.fa" not in commands
    assert "--split-candidates" in commands
    assert "--validate-candidates" in commands


def test_split_candidates_creates_single_chain_inputs(tmp_path):
    """The runtime split command preserves candidate provenance and chain count."""
    import json
    import subprocess

    from scripts.batch_runner import _SPLIT_CANDIDATES_SCRIPT

    sequence_dir = tmp_path / "sequences"
    sequence_dir.mkdir()
    (sequence_dir / "design.fa").write_text(">first\nAAAA\n>second\nBBBB\n", encoding="utf-8")
    (sequence_dir / "all_sequences.fa").write_text(">stale\nCCCC\n", encoding="utf-8")
    candidate_dir = tmp_path / "validation_inputs"

    command = [
        sys.executable,
        "-c",
        _SPLIT_CANDIDATES_SCRIPT,
        "--split-candidates",
        str(sequence_dir),
        str(candidate_dir),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stderr
    manifest = json.loads((candidate_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 2
    assert {item["sequence_id"] for item in manifest} == {"first", "second"}
    for item in manifest:
        payload = json.loads(Path(item["json"]).read_text(encoding="utf-8"))
        assert len(payload["sequences"]) == 1
        assert payload["sequences"][0]["protein"]["id"] == "A"
        assert payload["version"] == 1


def test_split_candidates_bounds_long_ids_with_stable_unique_hashes(tmp_path):
    """Long FASTA IDs must not create overlong or unstable Stage 3 filenames."""
    import json
    import re
    import subprocess

    from scripts.batch_runner import _SPLIT_CANDIDATES_SCRIPT

    sequence_dir = tmp_path / "sequences"
    sequence_dir.mkdir()
    long_id = "candidate_" + "X" * 400
    (sequence_dir / "long_source.fa").write_text(
        f">{long_id}\nAAAA\n>{long_id}\nBBBB\n", encoding="utf-8"
    )

    def split_into(candidate_dir):
        result = subprocess.run([
            sys.executable, "-c", _SPLIT_CANDIDATES_SCRIPT,
            "--split-candidates", str(sequence_dir), str(candidate_dir),
        ], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        return json.loads((candidate_dir / "manifest.json").read_text(encoding="utf-8"))

    first = split_into(tmp_path / "validation_inputs_one")
    second = split_into(tmp_path / "validation_inputs_two")
    first_names = [item["name"] for item in first]

    assert first_names == [item["name"] for item in second]
    assert len(first_names) == len(set(first_names)) == 2
    assert all(len(name) <= 120 for name in first_names)
    assert all(re.search(r"__[0-9a-f]{12}$", name) for name in first_names)
    for item in first:
        assert Path(item["fasta"]).name == f"{item['name']}.fa"
        assert Path(item["json"]).name == f"{item['name']}.json"
        assert json.loads(Path(item["json"]).read_text(encoding="utf-8"))["name"] == item["name"]
