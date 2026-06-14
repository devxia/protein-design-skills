"""Tests for protein_design.utils helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from protein_design.utils import (
    fasta_to_alphafold3_json,
    parse_confidence_json,
    read_fasta,
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
