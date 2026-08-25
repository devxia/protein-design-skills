"""Tests for scripts/run_alphafold3.py seed handling."""

from __future__ import annotations

import json

import scripts.run_alphafold3 as af3
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


# ---------------------------------------------------------------------------
# find_alphafold3 — config key resolution (alphafold3_path + legacy fallback)
# ---------------------------------------------------------------------------


def _write_script(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    return str(path)


def test_find_alphafold3_prefers_alphafold3_path_key(tmp_path):
    """alphafold3_path wins over the legacy alphafold_path key."""
    primary = _write_script(tmp_path / "primary" / "run_alphafold.py")
    legacy = _write_script(tmp_path / "legacy" / "run_alphafold.py")
    config = {"alphafold3_path": primary, "alphafold_path": legacy}
    assert af3.find_alphafold3(config) == primary


def test_find_alphafold3_falls_back_to_legacy_alphafold_path_key(tmp_path):
    """When alphafold3_path is unset/empty, the legacy alphafold_path is used."""
    legacy = _write_script(tmp_path / "legacy" / "run_alphafold.py")
    config = {"alphafold3_path": "", "alphafold_path": legacy}
    assert af3.find_alphafold3(config) == legacy


# ---------------------------------------------------------------------------
# run_alphafold3 — explicit notices for silently-ignored flags
# ---------------------------------------------------------------------------


class _FakeResult:
    returncode = 0
    stdout = ""
    stderr = ""


def _mock_run_alphafold3(monkeypatch, tmp_path, captured):
    """Hermetically mock a successful AlphaFold3 run; capture the argv used."""
    monkeypatch.setattr(af3, "get_config", lambda tool=None: {"output_dir": str(tmp_path)})
    monkeypatch.setattr(af3, "find_alphafold3", lambda config: "/fake/af3/run_alphafold.py")
    monkeypatch.setattr(af3, "log_history", lambda *a, **k: None)

    def fake_run(cmd, **kwargs):
        captured["cmd"] = [str(c) for c in cmd]
        return _FakeResult()

    monkeypatch.setattr(af3.subprocess, "run", fake_run)


def test_db_dir_ignored_with_no_msa_prints_notice(tmp_path, monkeypatch, capsys):
    """--db-dir together with --no-msa must not silently drop the db path (#31)."""
    json_path = tmp_path / "in.json"
    json_path.write_text(json.dumps({"name": "x", "modelSeeds": [1], "sequences": []}))
    captured: dict = {}
    _mock_run_alphafold3(monkeypatch, tmp_path, captured)

    rc = af3.run_alphafold3(
        str(json_path), str(tmp_path / "out"), db_dir="/some/db", run_data_pipeline=False
    )

    assert rc == 0
    joined = " ".join(captured["cmd"])
    assert "--db_dir" not in joined
    assert "--run_data_pipeline=false" in joined
    out = capsys.readouterr().out
    assert "--db-dir" in out and "/some/db" in out


def test_num_seeds_below_one_prints_notice(tmp_path, monkeypatch, capsys):
    """--num-seeds 0 must not be silently treated as 1 (#31)."""
    json_path = tmp_path / "in.json"
    json_path.write_text(json.dumps({"name": "x", "modelSeeds": [1], "sequences": []}))
    captured: dict = {}
    _mock_run_alphafold3(monkeypatch, tmp_path, captured)

    rc = af3.run_alphafold3(str(json_path), str(tmp_path / "out"), num_seeds=0)

    assert rc == 0
    # The original JSON is passed through unchanged (no seed expansion).
    joined = " ".join(captured["cmd"])
    assert str(json_path) in joined
    assert not list((tmp_path / "out").glob("*.seeds*.json"))
    out = capsys.readouterr().out
    assert "--num-seeds 0" in out
