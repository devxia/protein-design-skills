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
    discover_confidence_files,
    extract_content_text,
    fasta_to_alphafold3_json,
    get_config,
    get_hook_invoked_runner,
    hook_advisory_output,
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
    assert af3["dialect"] == "alphafold3"
    assert af3["version"] == 1
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
    assert ids[26] == "AA"
    assert len(ids) == len(set(ids))
    assert all(chain_id.isalpha() and chain_id.isupper() for chain_id in ids)


def test_fasta_to_alphafold3_json_supports_702_chains() -> None:
    af3 = fasta_to_alphafold3_json([(f"s{i}", "A") for i in range(702)])
    ids = [s["protein"]["id"] for s in af3["sequences"]]
    assert len(ids) == 702
    assert len(ids) == len(set(ids))
    assert all(chain_id.isalpha() and chain_id.isupper() for chain_id in ids)


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


def test_parse_confidence_json_rejects_non_finite_values(tmp_path: Path) -> None:
    """NaN and infinities must never enter confidence metrics or their means."""
    path = tmp_path / "confidence.json"
    path.write_text(json.dumps({
        "plddt": [80, "NaN", "Infinity", "-Infinity", 100],
        "iptm": "NaN",
        "ptm": float("inf"),
        "pae": [[2, "NaN"], [4, "Infinity"]],
    }), encoding="utf-8")

    assert parse_confidence_json(path) == pytest.approx({"plddt": 90.0, "pae": 3.0})


def test_parse_confidence_json_empty_list_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "confidence.json"
    path.write_text("[]")
    assert parse_confidence_json(path) == {}


def test_parse_confidence_json_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_confidence_json(tmp_path / "missing.json")


def test_parse_confidence_json_merges_alphafold3_detail_and_summary(tmp_path: Path) -> None:
    """One AlphaFold3 prediction must combine detail and summary metrics."""
    detailed = tmp_path / "job_confidences.json"
    summary = tmp_path / "job_summary_confidences.json"
    detailed.write_text(
        json.dumps({"atom_plddts": [80, 90], "pae": [[1, 3], [5, 7]], "ptm": "0.75"}),
        encoding="utf-8",
    )
    summary.write_text(
        json.dumps({"complex_plddt": 0.91, "complex_iptm": "0.82"}),
        encoding="utf-8",
    )

    expected = {"plddt": 85.0, "pae": 4.0, "ptm": 0.75, "iptm": 0.82}
    assert parse_confidence_json(detailed) == pytest.approx(expected)
    assert parse_confidence_json(summary) == pytest.approx(expected)


def test_parse_confidence_json_normalizes_complex_plddt(tmp_path: Path) -> None:
    path = tmp_path / "summary_confidences.json"
    path.write_text(json.dumps({"complex_plddt": "0.875"}), encoding="utf-8")
    assert parse_confidence_json(path)["plddt"] == pytest.approx(87.5)


def test_discover_confidence_files_deduplicates_af3_pair_and_keeps_boltz_models(
    tmp_path: Path,
) -> None:
    (tmp_path / "job_confidences.json").write_text("{}", encoding="utf-8")
    (tmp_path / "job_summary_confidences.json").write_text("{}", encoding="utf-8")
    model_one = tmp_path / "confidence_target_model_1.json"
    model_two = tmp_path / "confidence_target_model_2.json"
    model_one.write_text("{}", encoding="utf-8")
    model_two.write_text("{}", encoding="utf-8")

    discovered = discover_confidence_files(tmp_path)
    assert discovered == [
        tmp_path / "confidence_target_model_1.json",
        tmp_path / "confidence_target_model_2.json",
        tmp_path / "job_confidences.json",
    ]


def test_read_fasta_empty_file(tmp_path: Path) -> None:
    fa = tmp_path / "empty.fa"
    fa.write_text("")
    assert read_fasta(fa) == []


def test_write_fasta_empty(tmp_path: Path) -> None:
    out = tmp_path / "out.fa"
    write_fasta([], out)
    assert out.read_text() == ""


def test_read_fasta_skips_empty_header(tmp_path: Path) -> None:
    """A bare ">" header line is skipped rather than crashing."""
    fa = tmp_path / "seqs.fa"
    fa.write_text(
        ">seq1 description\n"
        "ACDEF\n"
        ">\n"
        "GHIKLM\n"
        ">seq2\n"
        "NPQRSTVWY\n"
    )
    seqs = read_fasta(fa)
    assert seqs == [
        ("seq1", "ACDEF"),
        ("seq2", "NPQRSTVWY"),
    ]


def test_read_fasta_leading_empty_header(tmp_path: Path) -> None:
    """An empty header before any real header yields no entries."""
    fa = tmp_path / "seqs.fa"
    fa.write_text(">\nACDEF\n")
    assert read_fasta(fa) == []


# ---------------------------------------------------------------------------
# log_history — side-channel log that never raises
# ---------------------------------------------------------------------------


def test_log_history_appends_record(monkeypatch, tmp_path: Path) -> None:
    """Success path: record structure, output_dir field, dir auto-creation."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not (tmp_path / ".protein-design").exists()

    from protein_design.utils import log_history

    log_history(
        "rfdiffusion",
        {"contig": "150-150", "num_designs": 5},
        runtime=12.5,
        success=True,
        output_dir="/out",
    )

    history_file = tmp_path / ".protein-design" / "history.jsonl"
    record = json.loads(history_file.read_text().strip())
    assert record["tool"] == "rfdiffusion"
    assert record["params"] == {"contig": "150-150", "num_designs": 5}
    assert record["runtime"] == 12.5
    assert record["success"] is True
    assert record["output_dir"] == "/out"
    assert "timestamp" in record


def test_log_history_open_failure_does_not_raise(monkeypatch, tmp_path: Path, capsys) -> None:
    """A failing open() (unwritable HOME, full disk) is warned, not raised."""
    import protein_design.utils as utils

    def raise_os_error(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(utils, "open", raise_os_error, raising=False)
    # Should not raise; warns on stderr instead.
    utils.log_history("tool", {}, runtime=1.0, success=True)
    assert "Warning: failed to log run history" in capsys.readouterr().err


def test_log_history_unserialisable_params_does_not_raise(monkeypatch, tmp_path: Path, capsys) -> None:
    """Params containing non-JSON-serialisable values are warned, not raised."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from protein_design.utils import log_history

    log_history("tool", {"pdb": Path("/some/structure.pdb")}, runtime=1.0, success=True)
    assert "Warning: failed to log run history" in capsys.readouterr().err


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


def test_get_config_alphafold3_path_env_wins_over_legacy_and_file(monkeypatch, tmp_path: Path) -> None:
    """ALPHAFOLD3_PATH beats the legacy ALPHAFOLD_PATH and any config-file value."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ALPHAFOLD3_PATH", "/env/af3")
    monkeypatch.setenv("ALPHAFOLD_PATH", "/env/legacy")
    cfg_dir = _make_config_dir(tmp_path)
    (cfg_dir / "config.yaml").write_text("alphafold3_path: /file/af3\n")

    config = get_config("alphafold3")
    assert config["alphafold3_path"] == "/env/af3"


def test_get_config_alphafold3_falls_back_to_legacy_env(monkeypatch, tmp_path: Path) -> None:
    """With ALPHAFOLD3_PATH unset, the documented legacy ALPHAFOLD_PATH is honoured."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ALPHAFOLD3_PATH", raising=False)
    monkeypatch.setenv("ALPHAFOLD_PATH", "/env/legacy")

    config = get_config("alphafold3")
    assert config["alphafold3_path"] == "/env/legacy"


def test_get_config_alphafold3_legacy_env_overrides_file(monkeypatch, tmp_path: Path) -> None:
    """The legacy ALPHAFOLD_PATH env var also takes precedence over the file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ALPHAFOLD3_PATH", raising=False)
    monkeypatch.setenv("ALPHAFOLD_PATH", "/env/legacy")
    cfg_dir = _make_config_dir(tmp_path)
    (cfg_dir / "config.yaml").write_text("alphafold3_path: /file/af3\n")

    config = get_config("alphafold3")
    assert config["alphafold3_path"] == "/env/legacy"


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


# ---------------------------------------------------------------------------
# extract_content_text — defensive tool-result payload extraction
# ---------------------------------------------------------------------------


def test_extract_content_text_happy_path() -> None:
    result = {"content": [{"text": "{\"ok\": 1}"}]}
    assert extract_content_text(result) == '{"ok": 1}'


def test_extract_content_text_malformed_shapes() -> None:
    """Malformed payloads return "" instead of raising (#27)."""
    # A direct string is a valid host response, not a malformed object.
    assert extract_content_text("not-a-dict") == "not-a-dict"
    assert extract_content_text({}) == ""
    assert extract_content_text({"content": "a-string"}) == ""
    assert extract_content_text({"content": []}) == ""
    assert extract_content_text({"content": ["not-a-dict"]}) == ""
    assert extract_content_text({"content": [None]}) == ""
    assert extract_content_text({"content": [{"text": 123}]}) == ""
    assert extract_content_text(None) == ""


# ---------------------------------------------------------------------------
# probe_gpus — shared nvidia-smi probe
# ---------------------------------------------------------------------------


def test_probe_gpus_parses_csv(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        class R:
            stdout = "NVIDIA A100, 40000\nNVIDIA L4, 2000\n"

        return R()

    import protein_design.utils as utils

    monkeypatch.setattr(utils.subprocess, "run", fake_run)
    assert utils.probe_gpus() == [
        {"name": "NVIDIA A100", "free_mb": 40000.0},
        {"name": "NVIDIA L4", "free_mb": 2000.0},
    ]


def test_probe_gpus_none_when_nvidia_smi_missing(monkeypatch) -> None:
    """Probe failure (missing nvidia-smi, timeout, nonzero exit) returns None (#29)."""
    import protein_design.utils as utils

    def raise_fnf(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(utils.subprocess, "run", raise_fnf)
    assert utils.probe_gpus() is None


def test_probe_gpus_empty_list_when_no_gpu(monkeypatch) -> None:
    """A working nvidia-smi reporting nothing means 'no GPU', not 'probe failed'."""
    import protein_design.utils as utils

    def fake_run(cmd, **kwargs):
        class R:
            stdout = ""

        return R()

    monkeypatch.setattr(utils.subprocess, "run", fake_run)
    assert utils.probe_gpus() == []


def test_get_hook_invoked_runner_accepts_only_structured_allowlisted_shell_commands():
    assert get_hook_invoked_runner({
        "tool_name": "Bash",
        "tool_input": {"command": "python scripts/run_boltz.py --out-dir outputs"},
    }) == "run_boltz"
    assert get_hook_invoked_runner({
        "tool_name": "PowerShell",
        "tool_input": {"command": r'python "C:\\repo path\\scripts\\run_omegafold.py" -o out'},
    }) == "run_omegafold"
    assert get_hook_invoked_runner({
        "tool_name": "Bash",
        "tool_input": {"command": "python scripts/run_boltz.py; echo injected"},
    }) is None
    assert get_hook_invoked_runner({
        "tool_name": "Bash",
        "tool_input": {"command": "python -c 'run_boltz.py'"},
    }) is None
    assert get_hook_invoked_runner({
        "tool_name": "Bash",
        "tool_input": {"command": "python scripts/not-run_boltz.py"},
    }) is None


def test_hook_advisory_output_has_portable_context_schema():
    assert json.loads(hook_advisory_output("Use a smaller batch.")) == {
        "hookSpecificOutput": {"additionalContext": "Use a smaller batch."}
    }
