"""Tests for scripts/summarize_outputs.py quality distribution."""

from __future__ import annotations

import json

from scripts.summarize_outputs import summarize


def _write_design(root, name: str, plddt: float) -> None:
    design_dir = root / name
    design_dir.mkdir()
    (design_dir / "confidence.json").write_text(
        json.dumps({"plddt": plddt, "iptm": 0.9, "ptm": 0.9}), encoding="utf-8"
    )


def test_quality_distribution_covers_all_designs(tmp_path):
    """The distribution must not be biased to the top-5 table entries."""
    for i in range(5):
        _write_design(tmp_path, f"design_top_{i}", 95.0)
    for i in range(5):
        _write_design(tmp_path, f"design_bad_{i}", 50.0)

    summary = summarize(tmp_path)

    dist = summary["quality_distribution"]
    assert dist == {"excellent": 5, "good": 0, "acceptable": 0, "poor": 5}

    # The top-5 table itself is unchanged: still 5 best designs.
    top = summary["top_designs"]
    assert len(top) == 5
    assert all(d["plddt"] == 95.0 for d in top)
