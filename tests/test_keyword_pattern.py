"""Canonical protein-keyword pattern + hooks.json matcher parity (#30)."""

from __future__ import annotations

import json
import re

from protein_design.utils import PROTEIN_DESIGN_KEYWORDS, PROTEIN_DESIGN_PATTERN
from tests.helpers import PROJECT_ROOT


def test_canonical_pattern_matches_keywords():
    pattern = re.compile(PROTEIN_DESIGN_PATTERN, re.IGNORECASE)
    assert pattern.search("Design a protein binder")
    assert pattern.search("run RFdiffusion on this PDB")
    assert not pattern.search("unrelated small talk")


def test_hooks_json_matcher_keyword_parity():
    """The declarative UserPromptSubmit matcher can never drift from the canonical set."""
    hooks_json = json.loads((PROJECT_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    groups = hooks_json["hooks"]["UserPromptSubmit"]
    assert len(groups) == 1
    matcher = groups[0]["matcher"]
    alternations = [g for g in re.findall(r"\(([^()]+)\)", matcher) if "|" in g]
    assert len(alternations) == 1, f"unexpected matcher shape: {matcher}"
    assert set(alternations[0].split("|")) == set(PROTEIN_DESIGN_KEYWORDS)


def test_rematching_hooks_use_canonical_pattern():
    """Hooks that re-match prompts must import the canonical pattern, not inline copies."""
    for name in ("session-health-check", "tool-recommender"):
        text = (PROJECT_ROOT / "protein_design" / "hooks" / f"{name}.py").read_text(encoding="utf-8")
        assert "PROTEIN_DESIGN_PATTERN" in text, f"{name} still uses an inline keyword regex"
