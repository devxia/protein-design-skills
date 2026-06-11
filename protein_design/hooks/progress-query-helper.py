#!/usr/bin/env python3
"""UserPromptSubmit hook: help users get progress summaries quickly.

When a user asks about progress, status, counts, or summaries, this hook
suggests the right command and prints a quick preview of available outputs.
It reduces friction for the "定期汇总" (periodic summary) workflow.

Enhancements over base version:
- Parses confidence.json files for quality metrics
- Detects completed pipeline stages from file patterns
- Recommends the next command based on missing stage
- Shows progress bars against detected or default expectations
- Bilingual keyword support (English + Chinese)
"""

import json
import sys
from pathlib import Path
from typing import Any


# Keywords that indicate the user wants a progress summary
PROGRESS_KEYWORDS = [
    "progress", "status", "summary", "summarize", "how many", "count of",
    "how many designs", "how many backbones", "how many sequences",
    "what is the output", "show output", "pipeline status", "current status",
    "progress report", "output count", "stage status",
    "进度", "状态", "汇总", "数量", "结果", "产物", "多少个",
    "完成了多少", "进行到哪一步", "当前进度", "设计了多少",
    "骨架数量", "序列数量", "验证数量", "有多少", "生成多少",
]


# Stage detection based on file patterns
STAGE_PATTERNS = {
    "preprocessing": {
        "patterns": ["*_fixed.pdb", "*/preprocessed/*.pdb"],
        "command": "python scripts/run_rfdiffusion.py --input-pdb <fixed_pdb> --contig \"150-150\" --num-designs 50",
        "hint": "Next: generate backbones with `scripts/run_rfdiffusion.py`",
    },
    "backbone": {
        "patterns": ["*.pdb"],
        "exclude": ["*_fixed.pdb"],
        "command": "python scripts/run_proteinmpnn.py --pdb-path \"outputs/backbones/*.pdb\" --out-folder outputs/seqs/ --num-seq 8",
        "hint": "Next: design sequences with `scripts/run_proteinmpnn.py`",
    },
    "sequence": {
        "patterns": ["*.fa", "*.fasta", "*.faa"],
        "command": "python scripts/convert_format.py --from fasta --to alphafold3_json --input outputs/seqs/seqs.fa --output outputs/af3_input.json",
        "hint": "Next: convert FASTA to AlphaFold3 JSON and validate structures",
    },
    "validation": {
        "patterns": ["confidence.json", "*.cif"],
        "command": "python scripts/run_filtering.py --results-dir outputs/af3/ --min-plddt 75 --top-n 10",
        "hint": "Next: run filtering to rank designs by pLDDT / ipTM thresholds",
    },
    "filtering": {
        "patterns": ["*summary*.csv", "*ranking*.json", "*/filtered/*"],
        "command": "python scripts/summarize_outputs.py --output-dir outputs/",
        "hint": "Pipeline complete! Review final summary with `scripts/summarize_outputs.py`",
    },
}


def _should_respond(prompt: str) -> bool:
    """Return True if the prompt is asking for progress/status info."""
    text_lower = prompt.lower()
    return any(kw in text_lower for kw in PROGRESS_KEYWORDS)


def _find_output_dir() -> Path:
    """Determine output directory from env > config > default > cwd."""
    candidates = [
        Path("outputs"),
        Path("/tmp/protein-design"),
        Path("."),
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return Path(".")


def _count_outputs(root: Path) -> dict[str, int]:
    """Count common artifact types under root."""
    counts: dict[str, int] = {"pdb": 0, "fasta": 0, "cif": 0, "confidence": 0}
    if not root.exists():
        return counts
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".pdb":
            counts["pdb"] += 1
        elif suffix in (".fa", ".fasta", ".faa"):
            counts["fasta"] += 1
        elif suffix == ".cif":
            counts["cif"] += 1
        elif path.name == "confidence.json":
            counts["confidence"] += 1
    return counts


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

    if "confidence" in data and isinstance(data["confidence"], dict):
        c = data["confidence"]
        for k in ("plddt", "iptm", "ptm"):
            v = c.get(k)
            if isinstance(v, (int, float)):
                metrics[k] = float(v)

    for k in ("plddt", "iptm", "ptm", "confidence_score"):
        if k not in metrics and isinstance(data.get(k), (int, float)):
            metrics[k] = float(data[k])

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


def _format_bar(pct: float, width: int = 20) -> str:
    """Render a Unicode progress bar."""
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:5.1f}%"


def _detect_stages(root: Path) -> dict[str, bool]:
    """Detect which pipeline stages appear complete from file patterns."""
    detected: dict[str, bool] = {}
    for stage, info in STAGE_PATTERNS.items():
        found = False
        for pattern in info.get("patterns", []):
            matches = list(root.rglob(pattern))
            exclude = info.get("exclude", [])
            matches = [m for m in matches if not any(m.match(e) for e in exclude)]
            if matches:
                found = True
                break
        detected[stage] = found
    return detected


def _recommend_next_stage(detected: dict[str, bool], counts: dict[str, int]) -> str:
    """Recommend the next pipeline stage and command."""
    # Filtering > validation > sequence > backbone > preprocessing
    if detected.get("validation") and not detected.get("filtering"):
        return STAGE_PATTERNS["filtering"]["hint"]
    if detected.get("sequence") and not detected.get("validation"):
        return STAGE_PATTERNS["validation"]["hint"]
    if detected.get("backbone") and not detected.get("sequence"):
        return STAGE_PATTERNS["sequence"]["hint"]
    if detected.get("preprocessing") and not detected.get("backbone"):
        return STAGE_PATTERNS["backbone"]["hint"]
    if counts["pdb"] == 0 and counts["fasta"] == 0 and counts["confidence"] == 0:
        return "Start the pipeline with `python scripts/run_pdbfixer.py --input target.pdb --output target_fixed.pdb`"
    return STAGE_PATTERNS["preprocessing"]["hint"]


def _build_response(output_dir: Path, counts: dict[str, int]) -> str:
    """Build a friendly bilingual response with commands the user can run."""
    lines: list[str] = []
    lines.append("📊 [Progress Helper / 进度助手] Current pipeline status / 当前流水线状态")
    lines.append("")

    stages = _detect_stages(output_dir)

    if counts["pdb"] == 0 and counts["fasta"] == 0 and counts["confidence"] == 0:
        lines.append("No output files detected yet in the default output directory.")
        lines.append("尚未在默认输出目录中检测到产物文件。请先运行一个流水线阶段，然后再查询。")
        lines.append("Run a pipeline stage first, then ask again or use the commands below / 先运行一个阶段，然后再询问或使用下方命令。")
    else:
        lines.append("Artifact Counts / 产物数量:")
        lines.append(f"   • Backbone / 骨架 PDB files:          {counts['pdb']:4d}")
        lines.append(f"   • Sequence / 序列 FASTA files:        {counts['fasta']:4d}")
        lines.append(f"   • Predicted structures / 预测结构:    {counts['cif']:4d}")
        lines.append(f"   • Confidence JSONs / 置信度文件:      {counts['confidence']:4d}")
        lines.append("")

        # Quality metrics
        conf_files = _find_confidence_files(output_dir)
        if conf_files:
            plddts: list[float] = []
            iptms: list[float] = []
            for conf_path in conf_files:
                metrics = _parse_confidence(conf_path)
                plddt = metrics.get("plddt")
                if plddt is not None:
                    plddts.append(plddt)
                iptm = metrics.get("iptm")
                if iptm is not None:
                    iptms.append(iptm)

            if plddts:
                dist = _quality_distribution(plddts)
                mean_plddt = sum(plddts) / len(plddts)
                lines.append("Quality Metrics / 质量指标:")
                lines.append(f"   • Mean pLDDT / 平均 pLDDT:           {mean_plddt:.1f}")
                if iptms:
                    lines.append(f"   • Mean ipTM / 平均 ipTM:             {sum(iptms)/len(iptms):.3f}")
                lines.append(f"   • Excellent (≥90) / 优秀:            {dist['excellent']}")
                lines.append(f"   • Good (80-89) / 良好:               {dist['good']}")
                lines.append(f"   • Acceptable (70-79) / 可接受:       {dist['acceptable']}")
                lines.append(f"   • Poor (<70) / 较差:                 {dist['poor']}")
                lines.append("")

        # Stage detection
        lines.append("Detected Stages / 已检测阶段:")
        stage_labels = {
            "preprocessing": ("🔧", "Preprocessing / 预处理"),
            "backbone": ("🦴", "Backbone generation / 骨架生成"),
            "sequence": ("🧬", "Sequence design / 序列设计"),
            "validation": ("🔬", "Structure validation / 结构验证"),
            "filtering": ("🏆", "Filtering / 筛选排序"),
        }
        for stage in ["preprocessing", "backbone", "sequence", "validation", "filtering"]:
            icon, label = stage_labels.get(stage, ("⬜", stage))
            status = "✅ complete / 已完成" if stages.get(stage) else "⬜ not detected / 未检测到"
            lines.append(f"   {icon} {label:40s} {status}")
        lines.append("")

    # Next step recommendation
    next_hint = _recommend_next_stage(stages, counts)
    lines.append(f"💡 {next_hint}")
    lines.append("")

    lines.append("Recommended Commands / 推荐命令:")
    lines.append("")
    lines.append("```bash")
    lines.append(f"# Project-wide dashboard / 项目级仪表盘")
    lines.append(f"python scripts/project_dashboard.py --output-dir {output_dir}")
    lines.append("")
    lines.append(f"# With expected counts / 带预期数量")
    lines.append(f"python scripts/project_dashboard.py --output-dir {output_dir} \\")
    lines.append(f"  --expected-backbones 50 \\")
    lines.append(f"  --expected-sequences 400 \\")
    lines.append(f"  --expected-validations 50")
    lines.append("")
    lines.append(f"# Live watch mode / 实时刷新 (每30秒)")
    lines.append(f"python scripts/project_dashboard.py --output-dir {output_dir} --watch")
    lines.append("")
    lines.append(f"# Single-directory summary / 单目录汇总")
    lines.append(f"python scripts/summarize_outputs.py --output-dir {output_dir}")
    lines.append("```")
    lines.append("")
    lines.append("The dashboard shows stage-by-stage progress, quality distribution, and next steps.")
    lines.append("仪表盘会显示分阶段进度、质量分布和下一步建议。")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    try:
        text = sys.stdin.read()
        data = json.loads(text) if text.strip() else {}
    except Exception:
        return 0

    prompt = str(data.get("user_prompt", ""))
    if not prompt or not _should_respond(prompt):
        return 0

    output_dir = _find_output_dir()
    counts = _count_outputs(output_dir)
    print(_build_response(output_dir, counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
