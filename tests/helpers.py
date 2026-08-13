"""Shared module-loading helpers for tests.

Hook and installer scripts use hyphenated filenames that cannot be
imported normally; load them by explicit file path instead.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_module_from_path(module_name: str, file_path: Path) -> ModuleType:
    """Load a module from an explicit file path and register it in sys.modules."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name!r} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_hook_module(name: str) -> ModuleType:
    """Load ``protein_design/hooks/<name>.py`` (hyphenated filename) as a module."""
    return load_module_from_path(
        name.replace("-", "_"),
        PROJECT_ROOT / "protein_design" / "hooks" / f"{name}.py",
    )


def load_install_hooks_module() -> ModuleType:
    """Load ``protein_design/hooks/install-hooks.py`` as an importable module."""
    return load_module_from_path(
        "install_hooks",
        PROJECT_ROOT / "protein_design" / "hooks" / "install-hooks.py",
    )
