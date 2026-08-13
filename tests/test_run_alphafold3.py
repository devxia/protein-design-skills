"""Tests for scripts/run_alphafold3.py seed handling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_alphafold3 import _set_model_seeds


def test_set_model_seeds_writes_range(tmp_path):
    p = tmp_path / "af3.json"
    p.write_text(json.dumps({"name": "x", "modelSeeds": [1], "sequences": []}))
    _set_model_seeds(str(p), 5)
    data = json.loads(p.read_text())
    assert data["modelSeeds"] == [1, 2, 3, 4, 5]


def test_set_model_seeds_preserves_other_fields(tmp_path):
    p = tmp_path / "af3.json"
    payload = {"name": "x", "modelSeeds": [1], "sequences": [{"protein": {"id": "A"}}]}
    p.write_text(json.dumps(payload))
    _set_model_seeds(str(p), 3)
    data = json.loads(p.read_text())
    assert data["name"] == "x"
    assert data["sequences"] == [{"protein": {"id": "A"}}]
    assert data["modelSeeds"] == [1, 2, 3]
