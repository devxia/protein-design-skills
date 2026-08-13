"""Tests for scripts/run_alphafold3.py seed handling."""

from __future__ import annotations

import json

from scripts.run_alphafold3 import _set_model_seeds


def test_set_model_seeds_writes_range(tmp_path):
    src = tmp_path / "af3.json"
    src.write_text(json.dumps({"name": "x", "modelSeeds": [1], "sequences": []}))
    out = tmp_path / "out" / "af3.seeds5.json"
    _set_model_seeds(str(src), 5, out)
    data = json.loads(out.read_text())
    assert data["modelSeeds"] == [1, 2, 3, 4, 5]


def test_set_model_seeds_preserves_other_fields(tmp_path):
    src = tmp_path / "af3.json"
    payload = {"name": "x", "modelSeeds": [1], "sequences": [{"protein": {"id": "A"}}]}
    src.write_text(json.dumps(payload))
    out = tmp_path / "out" / "af3.seeds3.json"
    _set_model_seeds(str(src), 3, out)
    data = json.loads(out.read_text())
    assert data["name"] == "x"
    assert data["sequences"] == [{"protein": {"id": "A"}}]
    assert data["modelSeeds"] == [1, 2, 3]


def test_set_model_seeds_never_mutates_user_input(tmp_path):
    """Seed expansion must write a copy and leave the original byte-identical (#21)."""
    src = tmp_path / "af3.json"
    original = json.dumps({"name": "x", "modelSeeds": [1], "sequences": []}, indent=2)
    src.write_text(original)
    out = tmp_path / "out" / "af3.seeds4.json"
    _set_model_seeds(str(src), 4, out)
    assert src.read_text() == original
    assert json.loads(out.read_text())["modelSeeds"] == [1, 2, 3, 4]
