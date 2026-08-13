"""Tests for protein_design.utils helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from protein_design.utils import (
    _escape_applescript,
    _escape_powershell,
    fasta_to_alphafold3_json,
    get_config,
    parse_confidence_json,
    read_fasta,
    send_notification,
    write_fasta,
)


def test_read_fasta_parses_multiline_sequence(tmp_path: Path) -> None:
    fa = tmp_path / "seqs.fa"
    fa.write_text(
        ">seq1 description\n"
        "ACDEF\n"
        "GHIKLM\n"
        ">seq2\n"
        "NPQRSTVWY\n"
    )
    seqs = read_fasta(fa)
    assert seqs == [
        ("seq1", "ACDEFGHIKLM"),
        ("seq2", "NPQRSTVWY"),
    ]


def test_write_fasta_round_trips(tmp_path: Path) -> None:
    out = tmp_path / "out.fa"
    seqs = [("A", "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY" * 2)]
    write_fasta(seqs, out)
    text = out.read_text()
    assert text.startswith(">A\n")
    lines = [line for line in text.splitlines() if not line.startswith(">")]
    assert all(len(line) <= 60 for line in lines)
    assert read_fasta(out) == seqs


def test_fasta_to_alphafold3_json() -> None:
    seqs = [("seq1", "ACDEF"), ("seq2", "GHIKL")]
    af3 = fasta_to_alphafold3_json(seqs, job_name="myjob", verbose=False)
    assert af3["name"] == "myjob"
    assert af3["modelSeeds"] == [1]
    assert len(af3["sequences"]) == 2
    assert af3["sequences"][0]["protein"]["id"] == "A"
    assert af3["sequences"][0]["protein"]["sequence"] == "ACDEF"
    assert af3["sequences"][1]["protein"]["id"] == "B"


def test_fasta_to_alphafold3_json_many_chains() -> None:
    seqs = [(f"s{i}", "A") for i in range(27)]
    af3 = fasta_to_alphafold3_json(seqs)
    ids = [s["protein"]["id"] for s in af3["sequences"]]
    assert ids[:26] == [chr(65 + i) for i in range(26)]
    assert ids[26] == "X26"


def _assert_approx(metrics: dict, key: str, value: Any) -> None:
    if isinstance(value, bool):
        assert metrics[key] is value
    elif isinstance(value, float):
        assert metrics[key] == pytest.approx(value)
    else:
        assert metrics[key] == value


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"confidence": {"plddt": 85.5, "iptm": 0.8, "ptm": 0.75}}, {"plddt": 85.5, "iptm": 0.8, "ptm": 0.75}),
        ({"plddt": 80.0, "iptm": 0.7, "ptm": 0.6, "has_clash": False}, {"plddt": 80.0, "iptm": 0.7, "ptm": 0.6, "has_clash": False}),
        ({"mean_plddt": 78.0}, {"plddt": 78.0}),
        ({"plddt": [80.0, 90.0, 70.0]}, {"plddt": 80.0}),
        ({"confidence": {"plddt": [80.0, 90.0]}}, {"plddt": 85.0}),
    ],
)
def test_parse_confidence_json(tmp_path: Path, payload: dict, expected: dict) -> None:
    path = tmp_path / "confidence.json"
    path.write_text(json.dumps(payload))
    metrics = parse_confidence_json(path)
    for key, value in expected.items():
        _assert_approx(metrics, key, value)


def test_parse_confidence_json_empty_list_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "confidence.json"
    path.write_text("[]")
    assert parse_confidence_json(path) == {}


def test_parse_confidence_json_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_confidence_json(tmp_path / "missing.json")


def test_read_fasta_empty_file(tmp_path: Path) -> None:
    fa = tmp_path / "empty.fa"
    fa.write_text("")
    assert read_fasta(fa) == []


def test_write_fasta_empty(tmp_path: Path) -> None:
    out = tmp_path / "out.fa"
    write_fasta([], out)
    assert out.read_text() == ""


# ---------------------------------------------------------------------------
# get_config — configuration resolution priority (env > file > defaults)
# ---------------------------------------------------------------------------


def _make_config_dir(home: Path) -> Path:
    cfg_dir = home / ".protein-design"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir


def test_get_config_env_overrides_file(monkeypatch, tmp_path: Path) -> None:
    """Explicitly set env vars take precedence over config file values."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PROTEIN_DESIGN_OUTPUT_DIR", "/from/env")
    cfg_dir = _make_config_dir(tmp_path)
    (cfg_dir / "config.yaml").write_text("output_dir: /from/file\n")

    config = get_config()
    assert config["output_dir"] == "/from/env"


def test_get_config_file_overrides_defaults_when_env_unset(monkeypatch, tmp_path: Path) -> None:
    """When an env var is not set, the config file value wins over the default."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PROTEIN_DESIGN_OUTPUT_DIR", raising=False)
    cfg_dir = _make_config_dir(tmp_path)
    (cfg_dir / "config.yaml").write_text("output_dir: /from/file\n")

    config = get_config()
    assert config["output_dir"] == "/from/file"


def test_get_config_uses_default_when_neither_set(monkeypatch, tmp_path: Path) -> None:
    """When neither env nor file provides a value, the built-in default is used."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PROTEIN_DESIGN_OUTPUT_DIR", raising=False)

    config = get_config()
    assert config["output_dir"] == "/tmp/protein-design"


def test_get_config_tool_path_env_overrides_file(monkeypatch, tmp_path: Path) -> None:
    """Tool-specific path env vars also take precedence over the file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RFDIFFUSION_PATH", "/env/rfd")
    cfg_dir = _make_config_dir(tmp_path)
    (cfg_dir / "config.yaml").write_text("rfdiffusion_path: /file/rfd\n")

    config = get_config("rfdiffusion")
    assert config["rfdiffusion_path"] == "/env/rfd"


def test_get_config_db_dir_empty_env_overrides_file(monkeypatch, tmp_path: Path) -> None:
    """An explicitly-empty db_dir env var overrides a non-empty file value."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ALPHAFOLD3_DB_DIR", "")
    cfg_dir = _make_config_dir(tmp_path)
    (cfg_dir / "config.yaml").write_text("db_dir: /from/file\n")

    config = get_config("alphafold3")
    assert config["db_dir"] == ""


def test_get_config_malformed_yaml_does_not_crash(monkeypatch, tmp_path: Path) -> None:
    """A malformed config file prints a traceback but returns defaults."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PROTEIN_DESIGN_OUTPUT_DIR", raising=False)
    cfg_dir = _make_config_dir(tmp_path)
    (cfg_dir / "config.yaml").write_text(": : : not valid yaml : : :\n")

    config = get_config()
    assert config["output_dir"] == "/tmp/protein-design"


# ---------------------------------------------------------------------------
# send_notification — best-effort, timeout-protected
# ---------------------------------------------------------------------------


def test_send_notification_swallows_failure(monkeypatch) -> None:
    """send_notification is best-effort: subprocess failure is silently ignored."""
    import protein_design.utils as utils

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "x", timeout=10)

    monkeypatch.setattr(utils.subprocess, "run", raise_timeout)
    # Should not raise.
    send_notification("title", "message")


def test_send_notification_passes_timeout(monkeypatch) -> None:
    """Every subprocess.run call from send_notification includes a timeout kwarg."""
    import protein_design.utils as utils

    captured: list[dict[str, Any]] = []

    def fake_run(*args, **kwargs):
        captured.append(kwargs)
        return None

    monkeypatch.setattr(utils.subprocess, "run", fake_run)
    monkeypatch.setattr(utils.platform, "system", lambda: "Darwin")
    send_notification("title", "message")
    assert len(captured) == 1
    assert "timeout" in captured[0]
    assert captured[0]["timeout"] == 10


def test_escape_powershell_hostile_strings() -> None:
    """PowerShell escaping must neutralize subexpressions, backticks, quotes, newlines (#20)."""
    assert _escape_powershell("$(whoami)") == "`$(whoami)"
    assert _escape_powershell("back`tick") == "back``tick"
    assert _escape_powershell('say "hi"') == 'say `"hi`"'
    assert _escape_powershell("line1\nline2\r\nline3\r") == "line1`nline2`nline3`n"
    # No raw $ or backtick survives unescaped.
    hostile = _escape_powershell('$x`$(calc)\n"')
    assert hostile == "`$x```$(calc)`n`\""


def test_escape_applescript_hostile_strings() -> None:
    """AppleScript escaping must flatten newlines and escape quotes/backslashes (#20)."""
    assert _escape_applescript("line1\nline2\r\nline3") == "line1 line2 line3"
    assert _escape_applescript('say "hi"') == 'say \\"hi\\"'
    assert _escape_applescript("back\\slash") == "back\\\\slash"


def test_run_notifier_uses_text_mode(monkeypatch) -> None:
    """The notifier subprocess call matches the documented subprocess style (#20)."""
    import protein_design.utils as utils

    captured: list[dict[str, Any]] = []

    def fake_run(*args, **kwargs):
        captured.append(kwargs)
        return None

    monkeypatch.setattr(utils.subprocess, "run", fake_run)
    monkeypatch.setattr(utils.platform, "system", lambda: "Darwin")
    send_notification("title", "message")
    assert captured[0].get("text") is True
