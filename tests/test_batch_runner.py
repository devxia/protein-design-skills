"""Tests for scripts/batch_runner.py config loading."""

from __future__ import annotations

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
