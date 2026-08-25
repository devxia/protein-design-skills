"""Regression tests for hook recommendation correctness fixes (batch 2).

Covers: execution-adapter payload schema tolerance / flag mapping,
alternative-tool-recommender trigger set, job-monitor & format-converter
trigger conditions, user-onboarding probe concurrency.
"""
from __future__ import annotations

import io
import json

from tests.helpers import load_hook_module as _load_hook_module


def _feed(monkeypatch, payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


# ---------------------------------------------------------------------------
# execution-adapter
# ---------------------------------------------------------------------------


def test_execution_adapter_flat_payload_with_no_msa(monkeypatch, capsys):
    """Flat shape {tool, tool_input}; use_msa_server=False maps to --no-msa."""
    module = _load_hook_module("execution-adapter")
    _feed(monkeypatch, {
        "tool": "boltz",
        "tool_input": {"input_path": "in.yaml", "use_msa_server": False},
    })
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "--no-msa" in out
    assert "--use_msa_server" not in out
    assert "--input in.yaml" in out


def test_execution_adapter_legacy_nested_payload(monkeypatch, capsys):
    """Legacy nested shape {params: {tool, params}} still works."""
    module = _load_hook_module("execution-adapter")
    _feed(monkeypatch, {
        "params": {
            "tool": "boltz",
            "params": {"input_path": "in.yaml", "use_msa_server": True},
        },
    })
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "--no-msa" not in out  # True → default MSA behaviour, no flag


def test_execution_adapter_hotspot_quoting(monkeypatch, capsys):
    """Direct-command hotspot override quotes each residue individually."""
    module = _load_hook_module("execution-adapter")
    _feed(monkeypatch, {
        "tool": "rfdiffusion",
        "tool_input": {"hotspot_res": ["A30", "A33"]},
    })
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert 'ppi.hotspot_res=["A30","A33"]' in out


def test_execution_adapter_survives_non_dict_json(monkeypatch, capsys):
    module = _load_hook_module("execution-adapter")
    _feed(monkeypatch, '["a-list", "not-a-dict"]')
    rc = module.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# alternative-tool-recommender
# ---------------------------------------------------------------------------


def test_alt_recommender_accepts_new_runner_tools(monkeypatch, capsys):
    module = _load_hook_module("alternative-tool-recommender")
    _feed(monkeypatch, {
        "tool": "run_boltz",
        "context": "Design a binder against my target protein",
    })
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "[Alternative Tool Recommender]" in out


def test_alt_recommender_survives_non_dict_json(monkeypatch, capsys):
    module = _load_hook_module("alternative-tool-recommender")
    _feed(monkeypatch, '"just a string"')
    rc = module.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# job-monitor / format-converter
# ---------------------------------------------------------------------------


def test_job_monitor_triggers_on_job_manager_tool(monkeypatch, capsys):
    module = _load_hook_module("job-monitor")
    _feed(monkeypatch, {"tool": "job_manager"})
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "[Job Monitor]" in out


def test_job_monitor_ignores_other_tools(monkeypatch, capsys):
    module = _load_hook_module("job-monitor")
    _feed(monkeypatch, {"tool": "run_rfdiffusion"})
    rc = module.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_format_converter_detects_sequences_from_run_script(monkeypatch, capsys):
    module = _load_hook_module("format-converter")
    result_text = json.dumps({"sequences": [">seq1 ACDE"], "output_path": "outputs/seqs/"})
    _feed(monkeypatch, {
        "tool": "run_proteinmpnn",
        "result": {"content": [{"text": result_text}]},
    })
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "convert_format.py" in out


# ---------------------------------------------------------------------------
# user-onboarding
# ---------------------------------------------------------------------------


def test_onboarding_probes_run_concurrently(monkeypatch):
    """Ten 2s probes must finish within the 5s hook budget (#29 pattern)."""
    import time

    module = _load_hook_module("user-onboarding")

    def slow_run(cmd, **kwargs):
        time.sleep(2)

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(module.subprocess, "run", slow_run)
    start = time.time()
    tools = module._check_tools()
    elapsed = time.time() - start
    assert elapsed < 5, f"probes appear sequential: {elapsed:.1f}s"
    assert len(tools) == 10
    assert all(v is True for v in tools.values())
