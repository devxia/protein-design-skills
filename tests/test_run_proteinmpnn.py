"""Regression tests for ProteinMPNN input expansion and output discovery."""

from __future__ import annotations

from pathlib import Path

import scripts.run_proteinmpnn as proteinmpnn


class _Result:
    returncode = 0
    stdout = ""
    stderr = ""


def _patch_runner(monkeypatch, tmp_path, write_output=True):
    calls = []

    monkeypatch.setattr(
        proteinmpnn,
        "get_config",
        lambda tool=None: {"output_dir": str(tmp_path / "history")},
    )
    monkeypatch.setattr(
        proteinmpnn,
        "find_proteinmpnn",
        lambda config: "/fake/protein_mpnn_run.py",
    )
    monkeypatch.setattr(proteinmpnn, "log_history", lambda *args, **kwargs: None)

    def fake_run(command, **kwargs):
        command = [str(token) for token in command]
        calls.append(command)
        if write_output:
            pdb_arg = Path(command[command.index("--pdb_path") + 1])
            output_dir = Path(command[command.index("--out_folder") + 1])
            output_file = output_dir / "seqs" / f"{pdb_arg.stem}.fa"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(f">{pdb_arg.stem}\nACDE\n", encoding="utf-8")
        return _Result()

    monkeypatch.setattr(proteinmpnn.subprocess, "run", fake_run)
    return calls


def test_glob_is_sorted_and_each_call_gets_one_pdb(tmp_path, monkeypatch):
    """A glob must expand into sorted, isolated single-file invocations."""
    (tmp_path / "b.pdb").write_text("END\n", encoding="utf-8")
    (tmp_path / "a.pdb").write_text("END\n", encoding="utf-8")
    calls = _patch_runner(monkeypatch, tmp_path)

    rc = proteinmpnn.run_proteinmpnn(
        str(tmp_path / "*.pdb"),
        str(tmp_path / "sequences"),
        num_seq_per_target=2,
    )

    assert rc == 0
    assert len(calls) == 2
    pdb_args = [call[call.index("--pdb_path") + 1] for call in calls]
    assert pdb_args == [str(tmp_path / "a.pdb"), str(tmp_path / "b.pdb")]
    assert all("*" not in value for value in pdb_args)
    output_args = [call[call.index("--out_folder") + 1] for call in calls]
    assert output_args[0] != output_args[1]
    assert all(Path(value).name in {"a", "b"} for value in output_args)


def test_nested_fasta_output_counts_only_new_files(tmp_path, monkeypatch, capsys):
    """The official ``<out_folder>/seqs`` layout is searched recursively."""
    output_dir = tmp_path / "sequences"
    stale = output_dir / "seqs" / "stale" / "old.fa"
    stale.parent.mkdir(parents=True)
    stale.write_text(">old\nAAAA\n", encoding="utf-8")
    pdb = tmp_path / "design.pdb"
    pdb.write_text("END\n", encoding="utf-8")
    _patch_runner(monkeypatch, tmp_path)

    rc = proteinmpnn.run_proteinmpnn(str(pdb), str(output_dir), verbose=True)

    assert rc == 0
    assert "FASTA files: 1" in capsys.readouterr().out


def test_stale_fasta_does_not_make_missing_run_succeed(tmp_path, monkeypatch, capsys):
    """A successful process with no fresh FASTA output must fail closed."""
    output_dir = tmp_path / "sequences"
    stale = output_dir / "seqs" / "old.fa"
    stale.parent.mkdir(parents=True)
    stale.write_text(">old\nAAAA\n", encoding="utf-8")
    pdb = tmp_path / "design.pdb"
    pdb.write_text("END\n", encoding="utf-8")
    _patch_runner(monkeypatch, tmp_path, write_output=False)

    rc = proteinmpnn.run_proteinmpnn(str(pdb), str(output_dir))

    assert rc == 3
    assert "No new FASTA output files" in capsys.readouterr().err
