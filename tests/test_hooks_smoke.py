"""Smoke-test every hook module.

Hooks that support --help are exercised through the CLI; the rest are at least
imported to verify they load without errors.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOKS = [
    p
    for p in sorted((PROJECT_ROOT / "protein_design" / "hooks").glob("*.py"))
    if p.name != "__init__.py"
]


def _import_hook(hook: Path) -> None:
    spec = importlib.util.spec_from_file_location(hook.stem, hook)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


@pytest.mark.parametrize("hook", HOOKS, ids=lambda p: p.name)
def test_hook_runs_or_imports(hook: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(hook), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        return

    # --help is not supported; importing must still succeed.
    _import_hook(hook)
