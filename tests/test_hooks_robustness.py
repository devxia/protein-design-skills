"""Behavior tests for hook input guards and output correctness (batch 2)."""

from __future__ import annotations

import io
import json

from tests.helpers import load_hook_module

_background_notify = load_hook_module("background-notify")
_design_complete_notify = load_hook_module("design-complete-notify")
_design_report = load_hook_module("design-report")
_error_recovery = load_hook_module("error-recovery")
_quality_gate = load_hook_module("quality-gate")


def _run_main(module, monkeypatch, capsys, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = module.main()
    captured = capsys.readouterr()
    return rc, captured


def test_background_notify_handles_timeout_event(monkeypatch, capsys):
    """hooks.json matches task.timeout — it must not be silently dropped."""
    sent = []
    monkeypatch.setattr(_background_notify, "send_notification", lambda t, m: sent.append((t, m)))
    rc, captured = _run_main(_background_notify, monkeypatch, capsys,
                             {"event": "task.timeout", "task_id": "abc123"})
    assert rc == 0
    assert len(sent) == 1
    assert "timed out" in sent[0][1].lower()
    assert "abc123" in sent[0][1]


def test_background_notify_ignores_unknown_event(monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(_background_notify, "send_notification", lambda t, m: sent.append((t, m)))
    rc, captured = _run_main(_background_notify, monkeypatch, capsys,
                             {"event": "task.started", "task_id": "abc123"})
    assert rc == 0
    assert sent == []


def test_complete_notify_formats_numeric_string_metric(monkeypatch, capsys):
    """JSON metrics may arrive as strings ("85.2") — formatting must not crash."""
    sent = []
    monkeypatch.setattr(_design_complete_notify, "send_notification", lambda t, m: sent.append((t, m)))
    inner = {
        "status": "completed",
        "task_id": "t1",
        "tool_name": "run_boltz",
        "result": {"metrics": {"mean_plddt": "85.2", "iptm": 0.8}},
    }
    payload = {"result": {"content": [{"text": json.dumps(inner)}]}}
    rc, captured = _run_main(_design_complete_notify, monkeypatch, capsys, payload)
    assert rc == 0
    assert "Traceback" not in captured.err
    assert sent and "pLDDT: 85.2" in sent[0][1]
    assert "ipTM: 0.800" in sent[0][1]


def test_complete_notify_survives_non_numeric_metric(monkeypatch, capsys):
    """Non-numeric metric text must fall back to the raw value, still exit 0."""
    sent = []
    monkeypatch.setattr(_design_complete_notify, "send_notification", lambda t, m: sent.append((t, m)))
    inner = {
        "status": "completed",
        "task_id": "t2",
        "result": {"metrics": {"mean_plddt": "n/a"}},
    }
    payload = {"result": {"content": [{"text": json.dumps(inner)}]}}
    rc, captured = _run_main(_design_complete_notify, monkeypatch, capsys, payload)
    assert rc == 0
    assert "Traceback" not in captured.err
    assert sent and "pLDDT: n/a" in sent[0][1]


def test_error_recovery_oom_requires_word_boundary():
    """Substrings like "bedroom" must not trigger the OOM path."""
    info = _error_recovery._parse_error("ValueError: bedroom layout mismatch in config")
    assert info["type"] != "gpu_error"
    assert info.get("subtype") != "oom"


def test_error_recovery_still_detects_real_oom():
    for text in [
        "RuntimeError: CUDA out of memory. Tried to allocate 2.0 GiB",
        "Process OOM killed by the kernel",
    ]:
        info = _error_recovery._parse_error(text)
        assert info["type"] == "gpu_error"
        assert info["subtype"] == "oom"


def test_design_report_honours_output_dir_env(monkeypatch, tmp_path):
    """PROTEIN_DESIGN_OUTPUT_DIR wins over the hard-coded /tmp default."""
    monkeypatch.setenv("PROTEIN_DESIGN_OUTPUT_DIR", str(tmp_path))
    found = _design_report._find_output_dir({})
    assert found is not None and found.resolve() == tmp_path.resolve()


def test_design_report_skips_scan_of_cwd(monkeypatch, capsys, tmp_path):
    """A bare filename in tool_input resolves its parent to the CWD — the hook
    must not rglob the whole working tree inside its time budget."""
    monkeypatch.chdir(tmp_path)
    payload = {"tool": "run_filtering", "tool_input": {"output_dir": "results.json"}}
    rc, captured = _run_main(_design_report, monkeypatch, capsys, payload)
    assert rc == 0
    assert captured.out == ""


def test_design_report_scans_explicit_output_dir(monkeypatch, capsys, tmp_path):
    (tmp_path / "design1").mkdir()
    (tmp_path / "design1" / "backbone.pdb").write_text("HEADER\n")
    payload = {"tool": "run_filtering", "tool_input": {"output_dir": str(tmp_path)}}
    rc, captured = _run_main(_design_report, monkeypatch, capsys, payload)
    assert rc == 0
    assert "[Design Report]" in captured.out
    assert "Backbone structures (.pdb):  1" in captured.out


def test_quality_gate_ignores_tool_name_in_unrelated_fields(monkeypatch, capsys):
    """An arbitrary payload field mentioning "boltz" must not trigger the gate
    when the explicit tool name is a non-validation tool."""
    payload = {
        "tool": "run_rfdiffusion",
        "result": {"content": [{"text": json.dumps({"metrics": {"mean_plddt": 90.0, "ptm": 0.8}})}]},
        "note": "remember to validate these with boltz-1 later",
    }
    rc, captured = _run_main(_quality_gate, monkeypatch, capsys, payload)
    assert rc == 0
    assert "[Quality Gate]" not in captured.out


def test_quality_gate_reads_explicit_tool_key(monkeypatch, capsys):
    payload = {
        "tool": "run_boltz",
        "result": {"content": [{"text": json.dumps({"metrics": {"mean_plddt": 90.0, "ptm": 0.8}})}]},
    }
    rc, captured = _run_main(_quality_gate, monkeypatch, capsys, payload)
    assert rc == 0
    assert "[Quality Gate]" in captured.out
