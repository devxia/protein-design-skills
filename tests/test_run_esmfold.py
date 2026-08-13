"""Tests for scripts/run_esmfold.py conformance (#22)."""

from __future__ import annotations

import scripts.run_esmfold as esmfold


def _write_fasta(path, content=">seq1 description\nMKVLA\nAGGV\n>seq2\nPPP\n"):
    path.write_text(content, encoding="utf-8")
    return path


def test_missing_esm_returns_exit_2_with_install_url(tmp_path, monkeypatch, capsys):
    """A missing ESM dependency must exit 2 as the docstring promises (#22)."""
    fasta = _write_fasta(tmp_path / "in.fa")
    monkeypatch.setattr(esmfold, "_check_esm_installed", lambda: False)

    rc = esmfold.run_esmfold_api(str(fasta), str(tmp_path / "out"))

    assert rc == 2
    err = capsys.readouterr().err
    assert "not installed" in err
    assert "github.com/facebookresearch/esm" in err


def test_probe_delegates_to_import_check(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(" ".join(map(str, cmd)))

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(esmfold.subprocess, "run", fake_run)
    assert esmfold._check_esm_installed() is True
    assert any("torch" in c and "esm" in c for c in calls)


def test_probe_false_when_import_fails(monkeypatch):
    def fake_run(cmd, **kwargs):
        class R:
            returncode = 1

        return R()

    monkeypatch.setattr(esmfold.subprocess, "run", fake_run)
    assert esmfold._check_esm_installed() is False


def test_output_dir_passed_via_argv_not_source_interpolation(tmp_path, monkeypatch):
    """Runtime paths reach the generated driver via argv, never interpolation (#22)."""
    fasta = _write_fasta(tmp_path / "in.fa")
    out_dir = tmp_path / 'out with "quote"'
    captured = {}

    monkeypatch.setattr(esmfold, "_check_esm_installed", lambda: True)
    monkeypatch.setattr(esmfold, "log_history", lambda *a, **k: None)

    def fake_run(cmd, **kwargs):
        captured["cmd"] = [str(c) for c in cmd]
        # Read the generated driver (argv[1] after the interpreter) before the
        # finally-block deletes it.
        captured["script"] = esmfold.Path(cmd[1]).read_text(encoding="utf-8")

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr(esmfold.subprocess, "run", fake_run)
    rc = esmfold.run_esmfold_api(str(fasta), str(out_dir), verbose=False)

    assert rc == 0
    # output_dir travels via argv, not source interpolation.
    assert captured["cmd"][-1] == str(out_dir)
    assert str(out_dir) not in captured["script"]
    assert "sys.argv[1]" in captured["script"]
    # Sequences are still parsed via the shared read_fasta (header id = first token).
    assert "seq1" in captured["script"]
    assert "seq2" in captured["script"]
