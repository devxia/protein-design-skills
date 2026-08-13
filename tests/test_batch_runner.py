"""Tests for scripts/batch_runner.py config loading."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.batch_runner import load_pipeline_config


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
    assert cmd[0] == "python"
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
