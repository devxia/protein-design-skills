#!/usr/bin/env python3
"""
Project-wide pipeline dashboard — progress summary.

Scans the project output directory across all stages and produces a consolidated
report of artifacts, quality metrics, and pipeline status. Useful for periodic
summaries and long-running design campaigns.

Replaces: periodic query_job polling across multiple tasks.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import parse_confidence_json

import argparse
import json
import time
from collections import defaultdict
from statistics import mean


def quality_bucket(plddt: float) -> str:
    if plddt >= 90:
        return "Excellent"
    if plddt >= 80:
        return "Good"
    if plddt >= 70:
        return "Acceptable"
    return "Poor"


def progress_bar(current: int, expected: int, width: int = 24) -> str:
    if expected <= 0:
        return "[░░░░░░░░░░░░░░░░░░░░░░░░]   N/A"
    pct = max(0.0, min(100.0, current / expected * 100))
    filled = int(round(width * pct / 100.0))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:5.1f}% ({current}/{expected})"


def discover_stages(root: Path) -> dict[str, dict]:
    """Discover pipeline stages by scanning subdirectories."""
    stages: dict[str, dict] = {
        "preprocessing": {"dir": root / "preprocessing", "label": "Stage 0: Preprocessing"},
        "backbone": {"dir": root / "backbone", "label": "Stage 1: Backbone Generation"},
        "sequence": {"dir": root / "sequence", "label": "Stage 2: Sequence Design"},
        "validation": {"dir": root / "validation", "label": "Stage 3: Structure Validation"},
        "filtering": {"dir": root / "filtering", "label": "Stage 4: Filtering"},
    }

    # Also accept common alternative names
    alt_names = {
        "preprocessing": ["pdbfixer", "fixed", "preprocess"],
        "backbone": ["rfdiffusion", "backbones", "designs"],
        "sequence": ["proteinmpnn", "seqs", "sequences"],
        "validation": ["alphafold3", "af3", "boltz", "chai1", "validated"],
        "filtering": ["filtered", "ranking"],
    }

    discovered: dict[str, dict] = {}
    for stage_key, info in stages.items():
        dirs_to_check = [info["dir"]]
        for alt in alt_names.get(stage_key, []):
            dirs_to_check.append(root / alt)

        for d in dirs_to_check:
            if d.exists() and d.is_dir():
                discovered[stage_key] = {"dir": d, "label": info["label"]}
                break

    # Fallback: scan any immediate subdirectories that look like stages
    if root.exists() and root.is_dir():
        for subdir in root.iterdir():
            if not subdir.is_dir():
                continue
            name = subdir.name.lower()
            for stage_key, alts in alt_names.items():
                if stage_key in discovered:
                    continue
                if any(a in name for a in alts + [stage_key]):
                    discovered[stage_key] = {"dir": subdir, "label": f"Stage ?: {subdir.name}"}
                    break

    return discovered


def count_stage_artifacts(stage_dir: Path) -> dict[str, int]:
    """Count artifact files in a stage directory."""
    return {
        "pdb": sum(1 for p in stage_dir.rglob("*.pdb")),
        "fasta": sum(1 for p in stage_dir.rglob("*.fa")) + sum(1 for p in stage_dir.rglob("*.fasta")),
        "cif": sum(1 for p in stage_dir.rglob("*.cif")),
        "confidence_json": sum(1 for p in stage_dir.rglob("confidence.json")),
        "filtered_json": 1 if (stage_dir / "filtered_results.json").exists() else 0,
    }


def collect_validation_metrics(stage_dir: Path) -> dict[str, list[float]]:
    """Collect validation metrics from confidence.json files."""
    metrics: dict[str, list[float]] = defaultdict(list)
    for conf_path in stage_dir.rglob("confidence.json"):
        try:
            conf = parse_confidence_json(conf_path)
        except Exception:
            continue
        for key, val in conf.items():
            metrics[key].append(val)
    return dict(metrics)


def stage_summary(stage_key: str, stage_dir: Path, expected: dict[str, int]) -> list[str]:
    """Generate summary lines for one stage."""
    lines: list[str] = []
    counts = count_stage_artifacts(stage_dir)

    if stage_key == "preprocessing":
        lines.append(f"   PDB files:        {counts['pdb']:4d}")
    elif stage_key == "backbone":
        expected_n = expected.get("backbones", 0)
        lines.append(f"   Backbone PDBs:    {counts['pdb']:4d}  {progress_bar(counts['pdb'], expected_n)}")
    elif stage_key == "sequence":
        expected_n = expected.get("sequences", 0)
        lines.append(f"   FASTA files:      {counts['fasta']:4d}  {progress_bar(counts['fasta'], expected_n)}")
    elif stage_key == "validation":
        expected_n = expected.get("validations", 0)
        lines.append(f"   Confidence JSONs: {counts['confidence_json']:4d}  {progress_bar(counts['confidence_json'], expected_n)}")
        lines.append(f"   Predicted CIFs:   {counts['cif']:4d}")

        metrics = collect_validation_metrics(stage_dir)
        if metrics.get("plddt"):
            plddts = metrics["plddt"]
            lines.append(f"   Mean pLDDT:       {mean(plddts):5.1f}  (best {max(plddts):.1f}, worst {min(plddts):.1f})")
            buckets = defaultdict(int)
            for p in plddts:
                buckets[quality_bucket(p)] += 1
            lines.append("   Quality dist:    " + "  ".join(f"{k}: {v}" for k, v in buckets.items()))
        if metrics.get("iptm"):
            iptms = metrics["iptm"]
            lines.append(f"   Mean ipTM:        {mean(iptms):5.3f}  (best {max(iptms):.3f})")
    elif stage_key == "filtering":
        lines.append(f"   Filtered results: {'yes' if counts['filtered_json'] else 'no'}")
        filtered_path = stage_dir / "filtered_results.json"
        if filtered_path.exists():
            try:
                with open(filtered_path, encoding="utf-8") as f:
                    data = json.load(f)
                total = data.get("total_designs", 0)
                passing = data.get("passing_designs", 0)
                lines.append(f"   Passing designs:  {passing}/{total}")
            except Exception:
                pass

    return lines


def build_dashboard(args) -> str:
    """Build the full dashboard string."""
    root = Path(args.output_dir).expanduser()
    stages = discover_stages(root)

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(" 🧬 Protein Design Pipeline Dashboard")
    lines.append(f" Project: {root}")
    lines.append(f" Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 72)
    lines.append("")

    expected = {
        "backbones": args.expected_backbones,
        "sequences": args.expected_sequences,
        "validations": args.expected_validations,
    }

    if not stages:
        lines.append("⚠️ No pipeline stages discovered yet.")
        lines.append(f"   Checked: {root}")
        lines.append("   Hint: Run a pipeline stage or point --output-dir at your outputs folder.")
        return "\n".join(lines)

    # Overall counts
    total_backbones = 0
    total_sequences = 0
    total_validations = 0
    for key, info in stages.items():
        counts = count_stage_artifacts(info["dir"])
        if key == "backbone":
            total_backbones += counts["pdb"]
        elif key == "sequence":
            total_sequences += counts["fasta"]
        elif key == "validation":
            total_validations += counts["confidence_json"]

    lines.append("📊 Overall Progress")
    lines.append(f"   Backbone PDBs:     {total_backbones:4d}")
    lines.append(f"   Sequence FASTAs:   {total_sequences:4d}")
    lines.append(f"   Validation JSONs:  {total_validations:4d}")
    lines.append("")

    # Stage details
    for key in ("preprocessing", "backbone", "sequence", "validation", "filtering"):
        if key not in stages:
            continue
        info = stages[key]
        lines.append(info["label"])
        lines.append(f"   Directory: {info['dir']}")
        lines.extend(stage_summary(key, info["dir"], expected))
        lines.append("")

    # Recommendations based on stage completion
    lines.append("🧭 Recommendations")
    if "backbone" not in stages:
        lines.append("   • Start with Stage 1: `python scripts/run_rfdiffusion.py ...`")
    elif "sequence" not in stages:
        lines.append("   • Continue to Stage 2: `python scripts/run_proteinmpnn.py ...`")
    elif "validation" not in stages:
        lines.append("   • Continue to Stage 3: `python scripts/run_alphafold3.py ...`")
    elif "filtering" not in stages:
        lines.append("   • Final stage: `python scripts/run_filtering.py ...`")
    else:
        lines.append("   • All stages detected. Review the Top Designs section above.")

    lines.append("")
    lines.append("💡 Tips")
    lines.append("   • Use --watch to refresh this dashboard every 30 seconds.")
    lines.append("   • Use --json to get machine-readable output for downstream scripts.")
    lines.append("   • Set --expected-* values to see progress bars against targets.")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Project-wide pipeline dashboard")
    parser.add_argument("--output-dir", "--out-dir", "-d", default="outputs", help="Project output directory")
    parser.add_argument("--expected-backbones", type=int, default=0, help="Expected backbone count")
    parser.add_argument("--expected-sequences", type=int, default=0, help="Expected sequence count")
    parser.add_argument("--expected-validations", type=int, default=0, help="Expected validation count")
    parser.add_argument("--watch", "-w", action="store_true", help="Refresh every 30 seconds")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args()

    try:
        while True:
            text = build_dashboard(args)
            if args.json:
                # Simple JSON would need structured data; for now just text
                print(json.dumps({"dashboard_text": text, "output_dir": str(args.output_dir)}))
            else:
                print(text)

            if not args.watch:
                break
            time.sleep(30)
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
