#!/usr/bin/env python3
"""PostToolUse hook: auto-generate design summary report after pipeline completion.

When the filtering stage completes, this hook scans output directories and
produces a real summary of designs with counts, rankings, and recommendations.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from protein_design.utils import parse_confidence_json
import traceback
import json
from typing import Any


def _find_output_dir(data: dict[str, Any]) -> Path | None:
    """Infer output directory from hook payload or common defaults."""
    # Try payload fields
    for key in ("output_dir", "output_dir", "results_dir", "output_prefix", "out_folder"):
        val = data.get("tool_input", {}).get(key) or data.get(key)
        if val:
            p = Path(str(val)).expanduser()
            if p.is_dir() or p.parent.is_dir():
                return p if p.is_dir() else p.parent
    # Common defaults
    for candidate in (Path("outputs"), Path("/tmp/protein-design")):
        if candidate.exists():
            return candidate
    return None


def _count_files(root: Path, suffixes: tuple[str, ...]) -> int:
    """Count files with any of the given suffixes."""
    count = 0
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            count += 1
    return count


def _collect_designs(root: Path) -> list[dict[str, Any]]:
    """Collect all validated designs sorted by pLDDT."""
    designs: list[dict[str, Any]] = []
    seen: set[str] = set()

    for conf_path in root.rglob("confidence.json"):
        try:
            metrics = parse_confidence_json(conf_path)
        except Exception:
            continue
        if metrics.get("plddt") is None:
            continue
        key = str(conf_path.resolve())
        if key in seen:
            continue
        seen.add(key)

        plddt = float(metrics["plddt"])
        iptm = metrics.get("iptm")
        ptm = metrics.get("ptm")

        quality = "Poor"
        if plddt >= 90:
            quality = "Excellent"
        elif plddt >= 80:
            quality = "Good"
        elif plddt >= 70:
            quality = "Acceptable"

        designs.append(
            {
                "id": conf_path.parent.name,
                "plddt": plddt,
                "iptm": float(iptm) if iptm is not None else None,
                "ptm": float(ptm) if ptm is not None else None,
                "quality": quality,
            }
        )

    designs.sort(key=lambda d: d["plddt"], reverse=True)
    return designs


def _load_filtered_results(root: Path) -> dict[str, Any] | None:
    """Load filtered_results.json produced by scripts/run_filtering.py."""
    path = root / "filtered_results.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _generate_report_from_filtered(
    out_dir: Path, filtered: dict[str, Any], lines: list[str]
) -> str:
    """Build report from structured filtered_results.json."""
    total = filtered.get("total_designs", 0)
    passing = filtered.get("passing_designs", 0)
    criteria = filtered.get("criteria", {})
    top_designs = filtered.get("top_designs", [])

    lines.append(f"✅ Filtered Designs: {passing}/{total} passed")
    lines.append(
        f"   Criteria: pLDDT ≥ {criteria.get('min_plddt', '?')}, "
        f"ipTM ≥ {criteria.get('min_iptm', '?')}, "
        f"pTM ≥ {criteria.get('min_ptm', '?')}, "
        f"PAE ≤ {criteria.get('max_pae', '?')}"
    )
    lines.append("")

    if top_designs:
        # Quality distribution
        buckets = {"Excellent": 0, "Good": 0, "Acceptable": 0, "Poor": 0}
        for d in top_designs:
            plddt = d.get("plddt", 0)
            if plddt >= 90:
                buckets["Excellent"] += 1
            elif plddt >= 80:
                buckets["Good"] += 1
            elif plddt >= 70:
                buckets["Acceptable"] += 1
            else:
                buckets["Poor"] += 1

        lines.append("🎯 Quality Distribution")
        for label, count in buckets.items():
            pct = count / len(top_designs) * 100 if top_designs else 0
            lines.append(f"   {label:<12} {count:3d} ({pct:5.1f}%)")
        lines.append("")

        lines.append("🏆 Top 5 Designs")
        lines.append(
            f"   {'Rank':<6}{'Name':<25}{'pLDDT':>8}{'ipTM':>8}{'pTM':>8}{'Score':>10}"
        )
        for i, d in enumerate(top_designs[:5], 1):
            plddt = d.get("plddt", 0)
            iptm = d.get("iptm")
            ptm = d.get("ptm")
            score = d.get("composite_score", 0)
            iptm_s = f"{iptm:.3f}" if isinstance(iptm, (int, float)) else "—"
            ptm_s = f"{ptm:.3f}" if isinstance(ptm, (int, float)) else "—"
            lines.append(
                f"   #{i:<5}{d.get('name', 'unknown'):<25}"
                f"{plddt:>8.1f}{iptm_s:>8}{ptm_s:>8}{score:>10.1f}"
            )
        lines.append("")

        top = top_designs[0]
        top_plddt = top.get("plddt", 0)
        top_iptm = top.get("iptm")
        lines.append("🔬 Recommendations")
        if top_plddt >= 90 and (top_iptm is None or top_iptm >= 0.85):
            lines.append("   • Lead candidate is excellent — proceed to gene synthesis.")
            lines.append("   • Order the top 1–3 designs for experimental validation.")
        elif top_plddt >= 80:
            lines.append("   • Top design is good — consider Rosetta relax or MD refinement.")
            lines.append("   • Run additional validators (Boltz-1 / Chai-1) for confidence.")
        else:
            lines.append("   • Top design is marginal — regenerate with adjusted parameters.")
            lines.append("   • Check input contig/hotspot definitions and increase num_designs.")
    else:
        lines.append("⚠️ No designs passed the filter.")
        lines.append("   Consider relaxing thresholds or generating more designs.")

    lines.append("")
    lines.append("🛠️ Next Steps")
    lines.append("   1. Review top designs in the table above.")
    lines.append("   2. Extract selected designs for experimental ordering.")
    lines.append("   3. Re-run with adjusted parameters if quality is insufficient.")
    lines.append(
        f"   4. Use `python scripts/summarize_outputs.py --output-dir {out_dir} --watch` "
        "for live updates."
    )

    return "\n".join(lines)


def _generate_report(data: dict[str, Any]) -> str:
    """Generate a markdown design report."""
    out_dir = _find_output_dir(data)
    if out_dir is None:
        out_dir = Path("outputs")

    lines: list[str] = []
    lines.append("📝 [Design Report] Pipeline Complete")
    lines.append("")

    # Artifact counts
    backbone_count = _count_files(out_dir, (".pdb",))
    sequence_count = _count_files(out_dir, (".fa", ".fasta", ".faa"))
    cif_count = _count_files(out_dir, (".cif", ".mmcif"))

    lines.append("📦 Generated Artifacts")
    lines.append(f"   • Backbone structures (.pdb):  {backbone_count}")
    lines.append(f"   • Sequence files (.fa/.fasta): {sequence_count}")
    lines.append(f"   • Predicted structures (.cif): {cif_count}")
    lines.append("")

    # Prefer structured filtered_results.json if run_filtering.py produced it
    filtered = _load_filtered_results(out_dir)
    if filtered and "top_designs" in filtered:
        return _generate_report_from_filtered(out_dir, filtered, lines)

    designs = _collect_designs(out_dir)

    if designs:
        lines.append(f"✅ Validated Designs: {len(designs)}")
        lines.append("")

        # Quality distribution
        buckets = {"Excellent": 0, "Good": 0, "Acceptable": 0, "Poor": 0}
        for d in designs:
            buckets[d["quality"]] += 1

        lines.append("🎯 Quality Distribution")
        for label, count in buckets.items():
            pct = count / len(designs) * 100
            lines.append(f"   {label:<12} {count:3d} ({pct:5.1f}%)")
        lines.append("")

        # Top designs
        lines.append("🏆 Top 5 Designs")
        lines.append(f"   {'Rank':<6}{'ID':<24}{'pLDDT':>8}{'ipTM':>8}{'pTM':>8}{'Quality':>10}")
        for i, d in enumerate(designs[:5], 1):
            iptm = f"{d['iptm']:.3f}" if d['iptm'] is not None else "—"
            ptm = f"{d['ptm']:.3f}" if d['ptm'] is not None else "—"
            lines.append(
                f"   #{i:<5}{d['id']:<24}{d['plddt']:>8.1f}{iptm:>8}{ptm:>8}{d['quality']:>10}"
            )
        lines.append("")

        # Recommendations based on top design quality
        top = designs[0]
        lines.append("🔬 Recommendations")
        if top["plddt"] >= 90 and (top["iptm"] is None or top["iptm"] >= 0.85):
            lines.append("   • Lead candidate is excellent — proceed to gene synthesis.")
            lines.append("   • Order the top 1–3 designs for experimental validation.")
        elif top["plddt"] >= 80:
            lines.append("   • Top design is good — consider Rosetta relax or MD refinement.")
            lines.append("   • Run additional validators (Boltz-1 / Chai-1) for confidence.")
        else:
            lines.append("   • Top design is marginal — regenerate with adjusted parameters.")
            lines.append("   • Check input contig/hotspot definitions and increase num_designs.")
    else:
        lines.append("⚠️ No validation metrics found yet.")
        lines.append("   Run filtering or check that confidence.json files exist under the output directory.")

    lines.append("")
    lines.append("🛠️ Next Steps")
    lines.append("   1. Review top designs in the table above.")
    lines.append("   2. Extract selected designs for experimental ordering.")
    lines.append("   3. Re-run with adjusted parameters if quality is insufficient.")
    lines.append(f"   4. Use `python scripts/summarize_outputs.py --output-dir {out_dir} --watch` for live updates.")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    try:
        input_data = sys.stdin.read()
        data = json.loads(input_data) if input_data.strip() else {}
    except json.JSONDecodeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    # Activate after filtering or when explicitly requested
    tool_name = str(data.get("tool", "")).lower()
    tool_input = data.get("tool_input", {})
    if isinstance(tool_input, dict):
        tool_name_alt = str(tool_input.get("tool", "")).lower()
    else:
        tool_name_alt = ""

    if "filter" not in tool_name and "filtering" not in tool_name_alt:
        return 0

    print(_generate_report(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
