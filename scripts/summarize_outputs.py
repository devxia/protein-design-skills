#!/usr/bin/env python3
"""Summarize protein design pipeline outputs.

Scans an output directory and reports counts of backbones, sequences,
validation results, and quality metrics. Designed for periodic progress
checks.

Examples:
    # One-shot summary
    python scripts/summarize_outputs.py --output-dir outputs/

    # Watch progress with auto-refresh (runs until interrupted)
    python scripts/summarize_outputs.py --output-dir outputs/ --watch --interval 30

    # Expected counts for progress percentage
    python scripts/summarize_outputs.py --output-dir outputs/ \
        --expected-backbones 50 --expected-sequences 200
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def _format_bar(pct: float, width: int = 24) -> str:
    """Render a Unicode progress bar."""
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:5.1f}%"


def _find_metrics_files(root: Path) -> list[Path]:
    """Find confidence JSON / summary CSV files under root."""
    metrics: list[Path] = []
    metrics.extend(root.rglob("confidence.json"))
    metrics.extend(root.rglob("*summary*.json"))
    metrics.extend(root.rglob("*result_summary*.csv"))
    metrics.extend(root.rglob("*_ranking.json"))
    return metrics


def _parse_confidence_json(path: Path) -> dict[str, Any]:
    """Parse AlphaFold3/Boltz/Chai confidence.json for key metrics."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    # Try multiple known schema variants
    metrics: dict[str, Any] = {}

    # AlphaFold3 schema
    if isinstance(data, dict):
        if "confidence" in data and isinstance(data["confidence"], dict):
            c = data["confidence"]
            metrics["plddt"] = c.get("plddt")
            metrics["iptm"] = c.get("iptm")
            metrics["ptm"] = c.get("ptm")
        if "ranking_score" in data:
            metrics["ranking_score"] = data["ranking_score"]
        if "model" in data and isinstance(data["model"], int):
            metrics["model"] = data["model"]

        # Boltz/Chai variants
        metrics.setdefault("plddt", data.get("plddt"))
        metrics.setdefault("iptm", data.get("iptm"))
        metrics.setdefault("ptm", data.get("ptm"))
        metrics.setdefault("confidence_score", data.get("confidence_score"))

    # Per-chain pLDDT list
    if "plddt" in data and isinstance(data["plddt"], list):
        plddts = [float(x) for x in data["plddt"] if isinstance(x, (int, float))]
        if plddts and metrics.get("plddt") is None:
            metrics["plddt"] = sum(plddts) / len(plddts)

    return {k: v for k, v in metrics.items() if v is not None}


def _count_by_suffix(root: Path, suffixes: tuple[str, ...]) -> int:
    """Count files with any of the given suffixes (case-insensitive)."""
    count = 0
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            count += 1
    return count


def _count_fasta(root: Path) -> int:
    """Count FASTA sequence files (.fa, .fasta, .faa)."""
    return _count_by_suffix(root, (".fa", ".fasta", ".faa"))


def _count_pdb(root: Path) -> int:
    """Count PDB structure files (.pdb)."""
    return _count_by_suffix(root, (".pdb",))


def _count_mmcif(root: Path) -> int:
    """Count mmCIF structure files (.cif)."""
    return _count_by_suffix(root, (".cif", ".mmcif"))


def _count_validation_jobs(root: Path) -> int:
    """Count validation result folders by confidence files."""
    return len(_find_metrics_files(root))


def _collect_top_designs(root: Path, top_n: int = 5) -> list[dict[str, Any]]:
    """Collect top designs sorted by average pLDDT."""
    designs: list[dict[str, Any]] = []
    seen: set[str] = set()

    for conf_path in _find_metrics_files(root):
        metrics = _parse_confidence_json(conf_path)
        if not metrics or metrics.get("plddt") is None:
            continue

        key = str(conf_path.resolve())
        if key in seen:
            continue
        seen.add(key)

        plddt = float(metrics["plddt"])
        iptm = metrics.get("iptm")
        ptm = metrics.get("ptm")

        designs.append(
            {
                "id": conf_path.parent.name,
                "path": str(conf_path.parent),
                "plddt": plddt,
                "iptm": float(iptm) if iptm is not None else None,
                "ptm": float(ptm) if ptm is not None else None,
            }
        )

    designs.sort(key=lambda d: d["plddt"], reverse=True)
    return designs[:top_n]


def _quality_distribution(designs: list[dict[str, Any]]) -> dict[str, int]:
    """Bucket designs by pLDDT ranges."""
    buckets = {"excellent": 0, "good": 0, "acceptable": 0, "poor": 0}
    for d in designs:
        p = d["plddt"]
        if p >= 90:
            buckets["excellent"] += 1
        elif p >= 80:
            buckets["good"] += 1
        elif p >= 70:
            buckets["acceptable"] += 1
        else:
            buckets["poor"] += 1
    return buckets


def summarize(root: Path, expected: dict[str, int] | None = None) -> dict[str, Any]:
    """Build a summary dict for the output directory."""
    expected = expected or {}
    summary: dict[str, Any] = {}

    summary["backbone_count"] = _count_pdb(root)
    summary["sequence_count"] = _count_fasta(root)
    summary["validation_count"] = _count_validation_jobs(root)
    summary["mmcif_count"] = _count_mmcif(root)

    top_designs = _collect_top_designs(root)
    summary["top_designs"] = top_designs
    summary["quality_distribution"] = _quality_distribution(top_designs)

    # Progress against expectations
    summary["progress"] = {}
    for key, label in [
        ("backbone_count", "backbones"),
        ("sequence_count", "sequences"),
        ("validation_count", "validations"),
    ]:
        expected_key = f"expected_{label}"
        if expected_key in expected and expected[expected_key] > 0:
            pct = summary[key] / expected[expected_key] * 100.0
            summary["progress"][label] = {
                "current": summary[key],
                "expected": expected[expected_key],
                "percent": round(pct, 1),
            }

    return summary


def _format_summary(summary: dict[str, Any], root: Path) -> str:
    """Render summary as a user-friendly markdown block."""
    lines: list[str] = []

    lines.append("📊 Protein Design Output Summary")
    lines.append(f"   Directory: {root}")
    lines.append("")

    # Artifact counts
    lines.append("🧬 Generated Artifacts")
    lines.append(f"   • Backbone structures (.pdb):   {summary['backbone_count']}")
    lines.append(f"   • Sequence files (.fa/.fasta):  {summary['sequence_count']}")
    lines.append(f"   • Validation results:           {summary['validation_count']}")
    lines.append(f"   • Predicted structures (.cif):  {summary['mmcif_count']}")
    lines.append("")

    # Progress bars
    if summary.get("progress"):
        lines.append("⏳ Progress")
        for label, info in summary["progress"].items():
            bar = _format_bar(info["percent"])
            lines.append(f"   {label.capitalize():14s} {bar}  ({info['current']}/{info['expected']})")
        lines.append("")

    # Quality distribution
    dist = summary.get("quality_distribution", {})
    total_validated = sum(dist.values())
    if total_validated > 0:
        lines.append("🎯 Validation Quality Distribution")
        lines.append(
            f"   Excellent (pLDDT ≥90): {dist['excellent']:3d}  "
            f"({dist['excellent']/total_validated*100:5.1f}%)"
        )
        lines.append(
            f"   Good      (80-90):     {dist['good']:3d}  "
            f"({dist['good']/total_validated*100:5.1f}%)"
        )
        lines.append(
            f"   Acceptable (70-80):    {dist['acceptable']:3d}  "
            f"({dist['acceptable']/total_validated*100:5.1f}%)"
        )
        lines.append(
            f"   Poor      (<70):       {dist['poor']:3d}  "
            f"({dist['poor']/total_validated*100:5.1f}%)"
        )
        lines.append("")

    # Top designs
    top = summary.get("top_designs", [])
    if top:
        lines.append("🏆 Top Designs by pLDDT")
        lines.append(f"   {'Rank':<6}{'ID':<20}{'pLDDT':>8}{'ipTM':>8}{'pTM':>8}")
        for i, d in enumerate(top, 1):
            iptm = f"{d['iptm']:.3f}" if d['iptm'] is not None else "—"
            ptm = f"{d['ptm']:.3f}" if d['ptm'] is not None else "—"
            lines.append(
                f"   #{i:<5}{d['id']:<20}{d['plddt']:>8.1f}{iptm:>8}{ptm:>8}"
            )
        lines.append("")

    lines.append(
        "💡 Tip: Run with --watch to refresh automatically, or pipe to a file for history."
    )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize protein design pipeline outputs."
    )
    parser.add_argument(
        "--output-dir",
        "-d",
        required=True,
        type=Path,
        help="Directory containing pipeline outputs.",
    )
    parser.add_argument(
        "--expected-backbones",
        type=int,
        default=0,
        help="Expected number of backbone PDB files for progress calculation.",
    )
    parser.add_argument(
        "--expected-sequences",
        type=int,
        default=0,
        help="Expected number of sequence FASTA files for progress calculation.",
    )
    parser.add_argument(
        "--expected-validations",
        type=int,
        default=0,
        help="Expected number of validation jobs for progress calculation.",
    )
    parser.add_argument(
        "--watch",
        "-w",
        action="store_true",
        help="Refresh summary repeatedly until interrupted.",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=30,
        help="Seconds between refreshes in watch mode (default: 30).",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Emit raw JSON instead of formatted text.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = args.output_dir.expanduser().resolve()
    if not root.exists():
        print(f"❌ Output directory not found: {root}", file=sys.stderr)
        return 1

    expected: dict[str, int] = {}
    if args.expected_backbones > 0:
        expected["expected_backbones"] = args.expected_backbones
    if args.expected_sequences > 0:
        expected["expected_sequences"] = args.expected_sequences
    if args.expected_validations > 0:
        expected["expected_validations"] = args.expected_validations

    try:
        while True:
            summary = summarize(root, expected)
            if args.json:
                print(json.dumps(summary, indent=2, ensure_ascii=False))
            else:
                # Clear screen in watch mode for clean display
                if args.watch:
                    print("\033[2J\033[H", end="")
                print(_format_summary(summary, root))

            if not args.watch:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n👋 Stopped watching.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
