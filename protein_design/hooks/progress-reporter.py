#!/usr/bin/env python3
"""PostToolUse hook: report progress with real output counts after pipeline stages.

Monitors output directories by counting files (PDB backbones, FASTA sequences,
validation results) and prints user-friendly progress summaries with
filesystem-aware progress tracking.
"""

import json
import sys
from pathlib import Path
from typing import Any


STAGE_TOOLS = {
    "run_pdbfixer": "preprocessing",
    "run_rfdiffusion": "backbone",
    "run_proteinmpnn": "sequence",
    "run_alphafold3": "validation",
    "run_boltz": "validation",
    "run_chai1": "validation",
    "run_esmfold": "validation",
    "run_omegafold": "validation",
    "run_openfold3": "validation",
    "run_protenix": "validation",
    "run_filtering": "filtering",
}

STAGE_HINTS: dict[str, str] = {
    "preprocessing": "✅ PDB fixed. Next: generate backbones with `scripts/run_rfdiffusion.py`.",
    "backbone": "💡 Next: Run ProteinMPNN to design sequences for the generated backbones.",
    "sequence": "💡 Next: Convert FASTA to AlphaFold3 JSON and validate structures.",
    "validation": "💡 Next: Run filtering to rank designs by pLDDT / ipTM thresholds.",
    "filtering": "🎉 Pipeline complete! Use `scripts/summarize_outputs.py` for the final report.",
}


def _find_output_dir(data: dict[str, Any]) -> Path | None:
    """Infer output directory from hook payload."""
    tool_input = data.get("tool_input", {}) if isinstance(data.get("tool_input", {}), dict) else {}
    for key in ("output_dir", "output_prefix", "results_dir", "out_folder"):
        val = tool_input.get(key)
        if val:
            p = Path(str(val)).expanduser()
            return p if p.is_dir() else p.parent
    # Fall back to common defaults
    for candidate in (Path("outputs"), Path("/tmp/protein-design")):
        if candidate.exists():
            return candidate
    return None


def _count_files(root: Path, suffixes: tuple[str, ...]) -> int:
    """Count files recursively under root with given suffixes."""
    count = 0
    try:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes:
                count += 1
    except Exception:
        pass
    return count


def _find_confidence_files(root: Path) -> list[Path]:
    """Find all confidence.json files under root."""
    try:
        return list(root.rglob("confidence.json"))
    except Exception:
        return []


def _parse_confidence(path: Path) -> dict[str, float]:
    """Parse a confidence.json file for pLDDT, ipTM, pTM."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    metrics: dict[str, float] = {}
    if not isinstance(data, dict):
        return metrics

    # AlphaFold3 nested schema
    if "confidence" in data and isinstance(data["confidence"], dict):
        c = data["confidence"]
        for k in ("plddt", "iptm", "ptm"):
            v = c.get(k)
            if isinstance(v, (int, float)):
                metrics[k] = float(v)

    # Flat schemas (Boltz, Chai, etc.)
    for k in ("plddt", "iptm", "ptm", "confidence_score"):
        if k not in metrics and isinstance(data.get(k), (int, float)):
            metrics[k] = float(data[k])

    # Per-residue pLDDT list → mean
    if "plddt" in data and isinstance(data["plddt"], list):
        vals = [float(x) for x in data["plddt"] if isinstance(x, (int, float))]
        if vals and "plddt" not in metrics:
            metrics["plddt"] = sum(vals) / len(vals)

    return metrics


def _quality_distribution(plddts: list[float]) -> dict[str, int]:
    """Bucket designs by pLDDT quality ranges."""
    buckets = {"excellent": 0, "good": 0, "acceptable": 0, "poor": 0}
    for p in plddts:
        if p >= 90:
            buckets["excellent"] += 1
        elif p >= 80:
            buckets["good"] += 1
        elif p >= 70:
            buckets["acceptable"] += 1
        else:
            buckets["poor"] += 1
    return buckets


def _format_progress_bar(pct: float, width: int = 24) -> str:
    """Render a Unicode progress bar."""
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:5.1f}%"


def _summarize(out_dir: Path, stage: str) -> str:
    """Build a progress summary for the given stage."""
    lines: list[str] = []
    lines.append(f"📈 [{stage.upper()} STAGE COMPLETE] Progress Summary")
    lines.append(f"   Output directory: {out_dir}")
    lines.append("")

    backbones = _count_files(out_dir, (".pdb",))
    sequences = _count_files(out_dir, (".fa", ".fasta", ".faa"))
    validations = _count_files(out_dir, (".cif", ".mmcif"))
    ensembles = _count_files(out_dir, (".xtc",))
    docked_poses = _count_files(out_dir, (".sdf",))
    confidence_files = _find_confidence_files(out_dir)
    confidence = len(confidence_files)

    lines.append("   Artifact Counts / 产物数量:")
    if stage == "preprocessing":
        lines.append(f"      • Preprocessed PDB files / 预处理 PDB: {backbones}")
    else:
        lines.append(f"      • Backbone PDB files / 骨架 PDB:     {backbones}")
    lines.append(f"      • Sequence FASTA files / 序列 FASTA:   {sequences}")
    lines.append(f"      • Predicted structures / 预测结构:     {validations}")
    if ensembles:
        lines.append(f"      • Ensemble trajectories / 构象系综轨迹: {ensembles}")
    if docked_poses:
        lines.append(f"      • Docked poses / 对接构象:             {docked_poses}")
    lines.append(f"      • Confidence JSON files / 置信度 JSON:  {confidence}")
    lines.append("")

    # Quality metrics for validation / filtering stages
    if stage in ("validation", "filtering") and confidence_files:
        plddts: list[float] = []
        iptms: list[float] = []
        top_designs: list[dict[str, Any]] = []

        for conf_path in confidence_files:
            metrics = _parse_confidence(conf_path)
            plddt = metrics.get("plddt")
            if plddt is None:
                continue
            plddts.append(plddt)
            iptm = metrics.get("iptm")
            top_designs.append({
                "id": conf_path.parent.name,
                "plddt": plddt,
                "iptm": iptm,
                "path": str(conf_path.parent),
            })
            if iptm is not None:
                iptms.append(iptm)

        if plddts:
            dist = _quality_distribution(plddts)
            mean_plddt = sum(plddts) / len(plddts)
            lines.append("   Quality Metrics / 质量指标:")
            lines.append(f"      • Mean pLDDT / 平均 pLDDT:           {mean_plddt:.1f}")
            if iptms:
                lines.append(f"      • Mean ipTM / 平均 ipTM:             {sum(iptms) / len(iptms):.3f}")
            lines.append(f"      • Excellent (≥90) / 优秀:            {dist['excellent']}")
            lines.append(f"      • Good (80-89) / 良好:               {dist['good']}")
            lines.append(f"      • Acceptable (70-79) / 可接受:       {dist['acceptable']}")
            lines.append(f"      • Poor (<70) / 差:                   {dist['poor']}")
            lines.append("")

            top_designs.sort(key=lambda d: d["plddt"], reverse=True)
            lines.append("   Top Designs by pLDDT / 按 pLDDT 排序的Top设计:")
            for d in top_designs[:3]:
                iptm_str = f" ipTM={d['iptm']:.3f}" if d["iptm"] is not None else ""
                lines.append(f"      • {d['id']}: pLDDT={d['plddt']:.1f}{iptm_str}")
            lines.append("")

    hint = STAGE_HINTS.get(stage, "💡 Continue with the next pipeline stage.")
    lines.append(f"   {hint}")

    lines.append("")
    lines.append(
        "   Tip: Watch live progress with `python scripts/summarize_outputs.py --output-dir "
        f"{out_dir} --watch`"
    )
    return "\n".join(lines)


def main() -> int:
    """Main entry point. Reads PostToolUse JSON from stdin."""
    try:
        input_data = sys.stdin.read()
        data = json.loads(input_data) if input_data.strip() else {}
    except Exception:
        return 0

    tool_name = str(data.get("tool", "")).lower()
    tool_input = data.get("tool_input", {})
    if isinstance(tool_input, dict):
        tool_name = tool_name or str(tool_input.get("tool", "")).lower()

    stage = None
    for name, label in STAGE_TOOLS.items():
        if name in tool_name:
            stage = label
            break

    if stage is None:
        return 0

    out_dir = _find_output_dir(data)
    if out_dir is None:
        return 0

    print(_summarize(out_dir, stage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
