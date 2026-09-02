"""All hooks must read stdin via the shared read_hook_input helper (#28)."""

from __future__ import annotations

import ast
import io
import json

from tests.helpers import PROJECT_ROOT, load_hook_module

# Hooks that consume the stdin payload. gpu-check-hook is excluded: it runs
# generic GPU/disk pre-checks and deliberately ignores the tool payload.
HOOK_FILES = sorted(
    p
    for p in (PROJECT_ROOT / "protein_design" / "hooks").glob("*.py")
    if p.name not in ("__init__.py", "install-hooks.py", "gpu-check-hook.py")
)

ALL_HOOK_FILES = sorted(
    p
    for p in (PROJECT_ROOT / "protein_design" / "hooks").glob("*.py")
    if p.name not in ("__init__.py", "install-hooks.py")
)


def test_hook_count():
    """Guard the hook inventory so the conformance tests stay comprehensive."""
    assert len(ALL_HOOK_FILES) == 22
    assert len(HOOK_FILES) == 21


def test_no_inline_stdin_reads_remain():
    for path in HOOK_FILES:
        text = path.read_text(encoding="utf-8")
        assert "sys.stdin.read()" not in text, f"inline stdin read remains in {path.name}"


def test_all_hooks_import_read_hook_input():
    for path in HOOK_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "protein_design.utils"
            for alias in node.names
        }
        assert "read_hook_input" in imported_names, (
            f"{path.name} does not import read_hook_input"
        )


def test_cost_estimator_reads_prompt_from_json_payload(monkeypatch, capsys):
    module = load_hook_module("cost-estimator")
    payload = {"prompt": "Design a protein binder with RFdiffusion"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "Cost Estimator" in out


def test_cost_estimator_ignores_keywords_outside_prompt(monkeypatch, capsys):
    """Keywords in unrelated JSON fields must not trigger prompt matching (#28)."""
    module = load_hook_module("cost-estimator")
    payload = {"session_id": "proteinmpnn-rfdiffusion", "prompt": "hello there"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "Cost Estimator" not in out


def test_user_onboarding_reads_prompt_from_json_payload(monkeypatch, capsys):
    """Onboarding must trigger on the standard "prompt" payload key."""
    module = load_hook_module("user-onboarding")
    monkeypatch.setattr(module, "_check_tools", lambda: {})
    payload = {"prompt": "Design a protein binder with RFdiffusion"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "Welcome to Protein Design" in out


def test_user_onboarding_ignores_keywords_outside_prompt(monkeypatch, capsys):
    """Keywords in unrelated JSON fields must not trigger onboarding."""
    module = load_hook_module("user-onboarding")
    monkeypatch.setattr(module, "_check_tools", lambda: {})
    payload = {"session_id": "rfdiffusion-proteinmpnn", "prompt": "hello there"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "Welcome to Protein Design" not in out


def test_progress_query_helper_reads_prompt_from_json_payload(monkeypatch, capsys, tmp_path):
    """The progress helper must trigger on the standard "prompt" payload key."""
    module = load_hook_module("progress-query-helper")
    monkeypatch.setattr(module, "_find_output_dir", lambda: tmp_path)
    payload = {"prompt": "How many designs have been generated so far?"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "Progress Helper" in out


def test_progress_query_helper_ignores_keywords_outside_prompt(monkeypatch, capsys):
    """Keywords in unrelated JSON fields must not trigger the progress helper."""
    module = load_hook_module("progress-query-helper")
    payload = {"session_id": "progress-summary", "prompt": "hello there"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = module.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "Progress Helper" not in out


def test_hooks_run_standalone_from_any_cwd(tmp_path):
    """Production fidelity: hooks execute as plain scripts with the repo root
    NOT importable (no PYTHONPATH, foreign cwd) — exactly how agents run them."""
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    for path in ALL_HOOK_FILES:
        proc = subprocess.run(
            [sys.executable, str(path)],
            input="{}",
            capture_output=True,
            text=True,
            cwd=tmp_path,
            env=env,
            timeout=60,
        )
        assert "ModuleNotFoundError" not in proc.stderr, f"{path.name}: {proc.stderr[-200:]}"
        assert "Traceback" not in proc.stderr, f"{path.name}: {proc.stderr[-200:]}"
