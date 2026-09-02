"""Tests for scripts/run_alphafold3.py seed handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.run_alphafold3 as af3
from protein_design.conda_utils import build_tool_command
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


def test_find_alphafold3_resolves_configured_directory(tmp_path):
    """A configured AlphaFold3 checkout resolves to its standard runner."""
    script = _write_script(tmp_path / "alphafold3" / "run_alphafold.py")
    assert af3.find_alphafold3({"alphafold3_path": str(Path(script).parent)}) == script


def test_find_alphafold3_conda_returns_real_script(monkeypatch):
    """Conda discovery must return run_alphafold.py, never a module command."""
    monkeypatch.setattr(af3.Path, "exists", lambda self: False)

    def fake_run(cmd, **kwargs):
        assert cmd[:5] == ["conda", "run", "-n", "alphafold3", "python"]
        assert cmd[5] == "-c"
        assert "pathlib" in cmd[6]
        return _FakeResult()

    result = _FakeResult()
    result.stdout = "/env/alphafold3/run_alphafold.py\n"
    monkeypatch.setattr(af3.subprocess, "run", lambda *args, **kwargs: result)

    found = af3.find_alphafold3({})

    assert found == "conda run -n alphafold3 python /env/alphafold3/run_alphafold.py"
    assert "-m alphafold3" not in found


def test_find_alphafold3_conda_round_trips_windows_script_path(monkeypatch):
    """Conda discovery must preserve spaced Windows paths as one argv item."""
    script = r"C:\\Program Files\\AlphaFold 3\\run_alphafold.py"
    result = _FakeResult()
    result.stdout = f"{script}\n"
    monkeypatch.setattr(af3.Path, "exists", lambda self: False)
    monkeypatch.setattr(af3.subprocess, "run", lambda *args, **kwargs: result)

    found = af3.find_alphafold3({})

    assert build_tool_command(found) == [
        "conda", "run", "-n", "alphafold3", "python", script,
    ]


def test_run_alphafold3_batch_calls_each_input_in_stable_isolated_directory(
    tmp_path, monkeypatch
):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    for name in ("z.json", "a b.json", "a_b.json"):
        (input_dir / name).write_text("{}")

    calls = []

    def fake_run(json_path, output_dir, **kwargs):
        calls.append((Path(json_path).name, Path(output_dir), kwargs))
        return 0

    monkeypatch.setattr(af3, "run_alphafold3", fake_run)
    output_dir = tmp_path / "outputs"

    rc = af3.run_alphafold3_batch(
        input_dir,
        output_dir,
        db_dir="/db",
        run_data_pipeline=False,
        num_seeds=4,
        verbose=True,
    )

    assert rc == 0
    assert [name for name, _, _ in calls] == ["a b.json", "a_b.json", "z.json"]
    task_dirs = [task_dir for _, task_dir, _ in calls]
    assert len(task_dirs) == len(set(task_dirs))
    assert all(task_dir.parent == output_dir for task_dir in task_dirs)
    assert all(task_dir.exists() for task_dir in task_dirs)
    assert all(call_kwargs == {
        "db_dir": "/db",
        "run_data_pipeline": False,
        "num_seeds": 4,
        "verbose": True,
    } for _, _, call_kwargs in calls)


def test_run_alphafold3_batch_returns_failure_and_attempts_remaining_inputs(
    tmp_path, monkeypatch
):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    (input_dir / "a.json").write_text("{}")
    (input_dir / "b.json").write_text("{}")
    calls = []

    def fake_run(json_path, output_dir, **kwargs):
        calls.append(Path(json_path).name)
        return 3 if Path(json_path).name == "a.json" else 0

    monkeypatch.setattr(af3, "run_alphafold3", fake_run)
    assert af3.run_alphafold3_batch(input_dir, tmp_path / "outputs") == 3
    assert calls == ["a.json", "b.json"]


def test_run_alphafold3_batch_empty_directory_returns_one(tmp_path, capsys):
    input_dir = tmp_path / "empty"
    input_dir.mkdir()
    assert af3.run_alphafold3_batch(input_dir, tmp_path / "outputs") == 1
    assert "No JSON input files" in capsys.readouterr().err


def test_alphafold3_parser_supports_single_or_batch_input():
    parser = af3.build_parser()
    single = parser.parse_args(["--json", "input.json", "--output-dir", "out"])
    batch = parser.parse_args(["--input-dir", "inputs", "--output-dir", "out", "--no-msa"])
    assert single.json == "input.json"
    assert single.input_dir is None
    assert batch.input_dir == "inputs"
    assert batch.json is None
    assert batch.no_msa is True
    with pytest.raises(SystemExit):
        parser.parse_args([
            "--json", "input.json", "--input-dir", "inputs", "--output-dir", "out"
        ])
