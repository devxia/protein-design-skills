"""Tests for scripts/run_pdbfixer.py (library wrapper approach)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_pdbfixer import PDBFIXER_WRAPPER, find_pdbfixer_python


def test_pdbfixer_wrapper_compiles():
    # The embedded wrapper is a string executed via `python -c`; a syntax
    # error there would surface only at runtime. Guard it at test time.
    compile(PDBFIXER_WRAPPER, "<pdbfixer-wrapper>", "exec")


def test_pdbfixer_wrapper_uses_library_interface():
    assert "PDBFixer(filename=" in PDBFIXER_WRAPPER
    assert "PDBFile.writeFile" in PDBFIXER_WRAPPER
    # Must not treat PDBFixer as a CLI.
    assert "argparse" not in PDBFIXER_WRAPPER


def test_find_pdbfixer_python_returns_none_when_missing(monkeypatch):
    import scripts.run_pdbfixer as rp

    monkeypatch.setattr(rp, "find_conda_env", lambda *a, **k: None)

    def raise_file_not_found(*a, **k):
        raise FileNotFoundError("python")

    monkeypatch.setattr(rp.subprocess, "run", raise_file_not_found)
    assert find_pdbfixer_python({}) is None


def test_find_pdbfixer_python_uses_current_interpreter(monkeypatch):
    import scripts.run_pdbfixer as rp

    monkeypatch.setattr(rp, "find_conda_env", lambda *a, **k: None)
    monkeypatch.setattr(rp.subprocess, "run", lambda *a, **k: _FakeResult())
    assert find_pdbfixer_python({}) == [sys.executable]


class _FakeResult:
    returncode = 0
    stdout = ""
    stderr = ""
