"""Shared pytest scaffolding for the protein-design-skills test suite.

Ensures the repository root is importable (for ``protein_design`` and
``scripts.*`` imports) regardless of pytest's import mode, so individual
test modules no longer need their own ``sys.path`` boilerplate.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
