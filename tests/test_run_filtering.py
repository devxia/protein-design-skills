"""Tests for scripts/run_filtering.py pure functions."""
import pytest

from scripts.run_filtering import compute_composite_score, filter_designs, parse_pdb_bfactor


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


def test_filter_designs_missing_plddt_fails_closed(tmp_path, capsys):
    """A confidence.json without pLDDT must not pass the pLDDT gate (#19)."""
    import json

    conf_dir = tmp_path / "design1"
    conf_dir.mkdir()
    (conf_dir / "confidence.json").write_text(
        json.dumps({"iptm": 0.9, "ptm": 0.9}), encoding="utf-8"
    )

    rc = filter_designs(str(tmp_path), min_plddt=70)
    assert rc == 0
    out = capsys.readouterr().out
    assert "0/1 designs passed" in out
    assert "missing" in out.lower()


def test_filter_designs_missing_dir(tmp_path):
    missing = tmp_path / "no_results"
    rc = filter_designs(str(missing))
    assert rc == 1


def test_filter_designs_dedupes_json_and_pdb_sources(tmp_path):
    """A directory with confidence.json AND a keyword PDB counts once."""
    import json

    conf_dir = tmp_path / "design1"
    conf_dir.mkdir()
    (conf_dir / "confidence.json").write_text(
        json.dumps({"plddt": 90.0}), encoding="utf-8"
    )
    (conf_dir / "pred_design1.pdb").write_text(
        "HEADER    test\n"
        "ATOM      1  N   ALA A   1      0.000   0.000   0.000  1.00 90.00           N\n"
        "ATOM      2  CA  ALA A   1      1.000   0.000   0.000  1.00 90.00           C\n"
        "END\n"
    )

    rc = filter_designs(str(tmp_path), min_plddt=70)
    assert rc == 0
    assert json.loads((tmp_path / "filtered_results.json").read_text(encoding="utf-8"))["total_designs"] == 1


def test_filter_designs_malformed_confidence_does_not_hide_pdb_fallback(tmp_path):
    """Only successfully parsed confidence JSON may suppress its PDB fallback."""
    import json

    result_dir = tmp_path / "design1"
    result_dir.mkdir()
    (result_dir / "confidence.json").write_text("{malformed", encoding="utf-8")
    pdb_file = result_dir / "model.pdb"
    pdb_file.write_text(
        "HEADER    test\n"
        "ATOM      1  N   ALA A   1      0.000   0.000   0.000  1.00 90.00           N\n"
        "ATOM      2  CA  ALA A   1      1.000   0.000   0.000  1.00 90.00           C\n"
        "END\n"
    )

    assert filter_designs(str(tmp_path), min_plddt=70) == 0
    results = json.loads((tmp_path / "filtered_results.json").read_text(encoding="utf-8"))
    assert results["total_designs"] == 1
    assert results["top_designs"][0]["path"] == str(pdb_file)


def test_filter_designs_discovers_filename_agnostic_pdb(tmp_path):
    """A valid PDB fallback is found even without a design-like filename."""
    import json

    pdb_file = tmp_path / "validator_output" / "model.pdb"
    pdb_file.parent.mkdir()
    pdb_file.write_text(
        "HEADER    test\n"
        "ATOM      1  N   ALA A   1      0.000   0.000   0.000  1.00 80.00           N\n"
        "ATOM      2  CA  ALA A   1      1.000   0.000   0.000  1.00 80.00           C\n"
        "END\n"
    )

    rc = filter_designs(str(tmp_path), min_plddt=70)
    assert rc == 0
    results = json.loads((tmp_path / "filtered_results.json").read_text(encoding="utf-8"))
    assert results["total_designs"] == 1
    assert results["passing_designs"] == 1
    assert results["top_designs"][0]["name"] == "model"


def test_filter_designs_pdb_dedup_only_skips_json_dirs(tmp_path):
    """A keyword PDB in a directory WITHOUT confidence.json still counts."""
    import json

    conf_dir = tmp_path / "design1"
    conf_dir.mkdir()
    (conf_dir / "confidence.json").write_text(
        json.dumps({"plddt": 90.0}), encoding="utf-8"
    )
    pdb_dir = tmp_path / "orf_only"
    pdb_dir.mkdir()
    (pdb_dir / "pred_orf.pdb").write_text(
        "HEADER    test\n"
        "ATOM      1  N   ALA A   1      0.000   0.000   0.000  1.00 80.00           N\n"
        "ATOM      2  CA  ALA A   1      1.000   0.000   0.000  1.00 80.00           C\n"
        "END\n"
    )

    rc = filter_designs(str(tmp_path), min_plddt=70)
    assert rc == 0
    results = json.loads((tmp_path / "filtered_results.json").read_text(encoding="utf-8"))
    assert results["total_designs"] == 2
    assert results["passing_designs"] == 2


def test_filter_designs_missing_metrics_wording_matches_behavior(tmp_path, capsys):
    """Only pLDDT is fail-closed; the printed note must say exactly that."""
    import json

    conf_dir = tmp_path / "design1"
    conf_dir.mkdir()
    (conf_dir / "confidence.json").write_text(
        json.dumps({"iptm": 0.9}), encoding="utf-8"
    )

    rc = filter_designs(str(tmp_path), min_plddt=70)
    assert rc == 0
    out = capsys.readouterr().out
    assert "only pLDDT is fail-closed" in out
    assert "missing metrics never pass the gate" not in out


def test_filter_designs_missing_iptm_passes_with_plddt(tmp_path):
    """Documents the behavior: missing ipTM/pTM/PAE do not block a design."""
    import json

    conf_dir = tmp_path / "design1"
    conf_dir.mkdir()
    (conf_dir / "confidence.json").write_text(
        json.dumps({"plddt": 80.0}), encoding="utf-8"
    )

    rc = filter_designs(str(tmp_path), min_plddt=70, min_iptm=0.6)
    assert rc == 0
    assert json.loads((tmp_path / "filtered_results.json").read_text(encoding="utf-8"))["passing_designs"] == 1
