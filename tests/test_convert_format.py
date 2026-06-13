"""Tests for scripts/convert_format.py pure functions."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.convert_format import (
    convert_format,
    csv_to_fasta,
    fasta_to_alphafold3_json,
    fasta_to_boltz_yaml,
    fasta_to_chai_fasta,
    pdb_to_fasta,
)


def test_fasta_to_alphafold3_json_basic():
    sequences = [("seq1", "ACDEFG")]
    result = fasta_to_alphafold3_json(sequences, job_name="test_job")
    assert result["name"] == "test_job"
    assert "sequences" in result
    assert result["sequences"][0]["protein"]["sequence"] == "ACDEFG"


def test_fasta_to_boltz_yaml_basic():
    sequences = [("seq1", "ACDEFG")]
    yaml = fasta_to_boltz_yaml(sequences)
    assert "sequences:" in yaml
    assert "sequence: ACDEFG" in yaml


def test_fasta_to_chai_fasta_basic():
    sequences = [("seq1", "ACDEFGHIJKLMNOPQRSTUVWXYZACDEFG")]
    fasta = fasta_to_chai_fasta(sequences)
    lines = fasta.splitlines()
    assert lines[0] == ">seq1|protein"
    assert lines[1] == "ACDEFGHIJKLMNOPQRSTUVWXYZACDEFG"


def test_csv_to_fasta(tmp_path):
    csv_file = tmp_path / "input.csv"
    csv_file.write_text("id,sequence\nseq1,ACDEFG\nseq2,GHKLMN\n")
    sequences = csv_to_fasta(str(csv_file))
    assert sequences == [("seq1", "ACDEFG"), ("seq2", "GHKLMN")]


def test_pdb_to_fasta(tmp_path):
    pdb_file = tmp_path / "tiny.pdb"
    pdb_file.write_text(
        "HEADER    test\n"
        "ATOM      1  N   ALA A   1      0.000   0.000   0.000  1.00 90.00           N\n"
        "ATOM      2  CA  ALA A   1      1.000   0.000   0.000  1.00 90.00           C\n"
        "ATOM      3  C   ALA A   1      2.000   0.000   0.000  1.00 90.00           C\n"
        "ATOM      4  O   ALA A   1      3.000   0.000   0.000  1.00 90.00           O\n"
        "ATOM      5  N   CYS A   2      4.000   0.000   0.000  1.00 80.00           N\n"
        "ATOM      6  CA  CYS A   2      5.000   0.000   0.000  1.00 80.00           C\n"
        "ATOM      7  C   CYS A   2      6.000   0.000   0.000  1.00 80.00           C\n"
        "ATOM      8  O   CYS A   2      7.000   0.000   0.000  1.00 80.00           O\n"
        "END\n"
    )
    sequences = pdb_to_fasta(str(pdb_file))
    assert sequences is not None
    assert len(sequences) == 1
    name, seq = sequences[0]
    assert "chain_A" in name
    assert seq == "AC"


def test_convert_format_fasta_to_af3(tmp_path):
    fasta = tmp_path / "input.fa"
    fasta.write_text(">seq1\nACDEFG\n")
    output = tmp_path / "out.json"
    rc = convert_format("fasta", "alphafold3_json", str(fasta), str(output), job_name="myjob")
    assert rc == 0
    data = json.loads(output.read_text())
    assert data["name"] == "myjob"


def test_convert_format_unsupported(tmp_path, capsys):
    fasta = tmp_path / "input.fa"
    fasta.write_text(">seq1\nACDEFG\n")
    output = tmp_path / "out.txt"
    rc = convert_format("fasta", "unsupported", str(fasta), str(output))
    assert rc == 2
