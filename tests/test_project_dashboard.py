"""Tests for scripts/project_dashboard.py structured data and utility docstrings (#26)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import scripts.project_dashboard as dash


def _args(output_dir):
    return SimpleNamespace(
        output_dir=str(output_dir),
        expected_backbones=10,
        expected_sequences=20,
        expected_validations=5,
    )


def _build_tree(root):
    (root / "backbone").mkdir(parents=True)
    (root / "backbone" / "d1.pdb").write_text("ATOM\n", encoding="utf-8")
    (root / "backbone" / "d2.pdb").write_text("ATOM\n", encoding="utf-8")
    (root / "sequence").mkdir()
    (root / "sequence" / "s1.fa").write_text(">x\nACD\n", encoding="utf-8")
    (root / "validation" / "v1").mkdir(parents=True)
    (root / "validation" / "v1" / "confidence.json").write_text(
        json.dumps({"plddt": 85.0, "iptm": 0.7}), encoding="utf-8"
    )
    (root / "validation" / "v2").mkdir()
    (root / "validation" / "v2" / "confidence.json").write_text(
        json.dumps({"plddt": 55.0}), encoding="utf-8"
    )
    (root / "filtering").mkdir()
    (root / "filtering" / "filtered_results.json").write_text(
        json.dumps({"total_designs": 2, "passing_designs": 1}), encoding="utf-8"
    )


def test_gather_dashboard_data_structure(tmp_path):
    """--json must emit structured, machine-readable data, not wrapped text (#26)."""
    _build_tree(tmp_path)
    data = dash.gather_dashboard_data(_args(tmp_path))

    assert data["totals"] == {"backbones": 2, "sequences": 1, "validations": 2}
    assert data["expected"]["backbones"] == 10
    assert "generated_at" in data

    validation = data["stages"]["validation"]
    assert validation["plddt"]["mean"] == 70.0
    assert validation["plddt"]["best"] == 85.0
    assert validation["plddt"]["worst"] == 55.0
    assert sum(validation["plddt"]["distribution"].values()) == 2
    assert validation["iptm"]["mean"] == 0.7

    filtering = data["stages"]["filtering"]["filtering"]
    assert filtering == {"total_designs": 2, "passing_designs": 1}

    # The --json contract: serializable as-is.
    json.dumps(data)


def test_summarize_outputs_has_module_docstring():
    """The module docstring must sit above the future import and list exit codes (#26)."""
    import scripts.summarize_outputs as summ

    assert summ.__doc__ and "Exit codes" in summ.__doc__
