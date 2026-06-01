"""Filtering and ranking tool for protein design validation results.

Filters designs by AlphaFold3 confidence metrics and ranks them by
a composite quality score.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _compute_quality_score(design: dict[str, Any]) -> float:
    """Compute a composite quality score for ranking.

    Weights:
        - pLDDT (mean): 40%
        - ipTM: 35%
        - pTM: 25%

    Args:
        design: Design dict with metrics.

    Returns:
        Composite score (higher is better).
    """
    metrics = design.get("metrics", {})

    plddt = metrics.get("mean_plddt", 0)
    iptm = metrics.get("iptm", 0)
    ptm = metrics.get("ptm", 0)

    # Normalize pLDDT to 0-1 scale
    plddt_norm = min(plddt / 100.0, 1.0)

    # ipTM and pTM are already 0-1
    iptm_norm = min(max(iptm, 0), 1)
    ptm_norm = min(max(ptm, 0), 1)

    score = plddt_norm * 0.40 + iptm_norm * 0.35 + ptm_norm * 0.25
    return round(score, 4)


def run_filtering(params: dict[str, Any], progress_callback: callable) -> dict[str, Any]:
    """Filter and rank protein designs by quality metrics.

    Args:
        params: Dict with designs list and optional criteria.
        progress_callback: Function(progress: int) to report progress.

    Returns:
        Result dict with filtered designs, rankings, and summary.
    """
    progress_callback(10)

    designs = params.get("designs", [])
    if not designs:
        return {
            "status": "completed",
            "filtered_designs": [],
            "summary": {"total": 0, "passed": 0, "failed": 0},
        }

    criteria = params.get("criteria", {})
    min_plddt = criteria.get("min_plddt", 70)
    min_iptm = criteria.get("min_iptm", 0.6)
    min_ptm = criteria.get("min_ptm", 0.5)
    allow_clashes = criteria.get("allow_clashes", False)

    progress_callback(30)

    filtered = []
    failed = []

    for design in designs:
        metrics = design.get("metrics", {})
        passed = True
        reasons = []

        plddt = metrics.get("mean_plddt")
        if plddt is not None and plddt < min_plddt:
            passed = False
            reasons.append(f"pLDDT {plddt:.1f} < {min_plddt}")

        iptm = metrics.get("iptm")
        if iptm is not None and iptm < min_iptm:
            passed = False
            reasons.append(f"ipTM {iptm:.3f} < {min_iptm}")

        ptm = metrics.get("ptm")
        if ptm is not None and ptm < min_ptm:
            passed = False
            reasons.append(f"pTM {ptm:.3f} < {min_ptm}")

        has_clash = metrics.get("has_clash", False)
        if has_clash and not allow_clashes:
            passed = False
            reasons.append("has_clash=true")

        design["quality_score"] = _compute_quality_score(design)
        design["filter_status"] = "pass" if passed else "fail"
        design["filter_reasons"] = reasons

        if passed:
            filtered.append(design)
        else:
            failed.append(design)

    progress_callback(70)

    # Sort by quality score descending
    filtered.sort(key=lambda d: d["quality_score"], reverse=True)

    # Add rank
    for i, design in enumerate(filtered, 1):
        design["rank"] = i

    progress_callback(100)

    return {
        "status": "completed",
        "filtered_designs": filtered,
        "failed_designs": failed,
        "summary": {
            "total": len(designs),
            "passed": len(filtered),
            "failed": len(failed),
            "criteria": {
                "min_plddt": min_plddt,
                "min_iptm": min_iptm,
                "min_ptm": min_ptm,
                "allow_clashes": allow_clashes,
            },
        },
    }
