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
    """Hooks that re-match prompts must build on the canonical keyword set, not inline copies."""
    for name in (
        "session-health-check",
        "tool-recommender",
        "auto-parameter-tuner",
        "cost-estimator",
        "parameter-generator",
    ):
        text = (PROJECT_ROOT / "protein_design" / "hooks" / f"{name}.py").read_text(encoding="utf-8")
        uses_canonical = "PROTEIN_DESIGN_PATTERN" in text or "protein_keyword_pattern" in text
        assert uses_canonical, f"{name} still uses an inline keyword regex"
        assert 'r"\\b(protein|' not in text and "r'\\b(protein|" not in text, name


def test_protein_keyword_pattern_extends_canonical():
    """Hook-specific extras extend, never replace, the canonical keyword set."""
    from protein_design.utils import protein_keyword_pattern

    extended = re.compile(protein_keyword_pattern(("cost", "gpu")), re.IGNORECASE)
    assert extended.search("protein design")
    assert extended.search("how much GPU time")
    bare = re.compile(protein_keyword_pattern(), re.IGNORECASE)
    assert bare.search("binder scaffold")
    assert not bare.search("how much GPU time")
