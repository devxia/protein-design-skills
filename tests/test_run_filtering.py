"""Tests for scripts/run_filtering.py pure functions."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_filtering import compute_composite_score, parse_pdb_bfactor


def test_compute_composite_score_plddt_only():
    result = {"plddt": 80.0}
    weights = {"plddt": 1.0, "iptm": 0.0, "ptm": 0.0, "pae": 0.0}
    assert compute_composite_score(result, weights) == pytest.approx(80.0)


def test_compute_composite_score_with_iptm_and_ptm():
    result = {"plddt": 80.0, "iptm": 0.8, "ptm": 0.85}
    weights = {"plddt": 0.5, "iptm": 0.3, "ptm": 0.2, "pae": 0.0}
    expected = (80.0 * 0.5 + 0.8 * 100 * 0.3 + 0.85 * 100 * 0.2) / (0.5 + 0.3 + 0.2)
    assert compute_composite_score(result, weights) == pytest.approx(expected)


def test_compute_composite_score_with_pae():
    result = {"pae": 5.0}
    weights = {"plddt": 0.0, "iptm": 0.0, "ptm": 0.0, "pae": 1.0}
    expected = max(0, 100 - 5.0 * 10)
    assert compute_composite_score(result, weights) == pytest.approx(expected)


def test_compute_composite_score_no_metrics():
    assert compute_composite_score({}, {"plddt": 1.0}) == 0.0


def test_parse_pdb_bfactor(tmp_path):
    pdb_file = tmp_path / "pred.pdb"
    pdb_file.write_text(
        "HEADER    test\n"
        "ATOM      1  N   ALA A   1      0.000   0.000   0.000  1.00 85.00           N\n"
        "ATOM      2  CA  ALA A   1      1.000   0.000   0.000  1.00 85.00           C\n"
        "ATOM      3  N   CYS A   2      2.000   0.000   0.000  1.00 75.00           N\n"
        "ATOM      4  CA  CYS A   2      3.000   0.000   0.000  1.00 75.00           C\n"
        "END\n"
    )
    mean_b = parse_pdb_bfactor(str(pdb_file))
    assert mean_b == pytest.approx(80.0)


def test_parse_pdb_bfactor_missing_file():
    assert parse_pdb_bfactor("/nonexistent/path.pdb") is None
