#!/usr/bin/env python3
"""PostToolUse hook: enforce quality gates after validation stage.

After structure prediction completes, this hook checks confidence metrics
against project-specific thresholds and provides clear pass/fail decisions
with actionable next steps — reducing manual review overhead.
"""
import traceback
import json
from typing import Any
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from protein_design.utils import extract_content_text, read_hook_input


THRESHOLDS: dict[str, dict[str, float]] = {
    "binder": {
        "min_plddt": 80.0,
        "min_iptm": 0.80,
        "min_ptm": 0.70,
    },
    "monomer": {
        "min_plddt": 80.0,
        "min_ptm": 0.70,
    },
    "peptide": {
        "min_plddt": 70.0,
        "min_iptm": 0.60,
    },
    "enzyme": {
        "min_plddt": 75.0,
        "min_ptm": 0.65,
    },
    "relaxed": {
        "min_plddt": 70.0,
        "min_ptm": 0.50,
    },
}


def _extract_metrics(result: dict[str, Any]) -> dict[str, float]:
    """Extract confidence metrics from tool result."""
    metrics: dict[str, float] = {}

    # Try different result formats
    if "metrics" in result:
        m = result["metrics"]
        for key in ["mean_plddt", "plddt", "iptm", "ipTM", "ptm", "pTM"]:
            if key in m:
                metrics[key.lower().replace("mean_", "")] = float(m[key])
    elif "plddt" in result:
        metrics["plddt"] = float(result["plddt"])
    elif "confidence" in result:
        c = result["confidence"]
        for key in ["plddt", "iptm", "ptm"]:
            if key in c:
                metrics[key] = float(c[key])

    return metrics


def _detect_design_type(result: dict[str, Any]) -> str:
    """Detect design type from result metadata."""
    # Check for binder indicators
    if "binder" in str(result).lower():
        return "binder"
    if "peptide" in str(result).lower():
        return "peptide"
    if "enzyme" in str(result).lower():
        return "enzyme"
    return "monomer"


def _evaluate_quality(metrics: dict[str, float], design_type: str) -> dict[str, Any]:
    """Evaluate metrics against thresholds."""
    thresholds = THRESHOLDS.get(design_type, THRESHOLDS["monomer"])

    passed = []
    failed = []

    for metric, threshold in thresholds.items():
        # Threshold keys are prefixed with "min_"; extracted metric keys are
        # not (e.g. "min_plddt" vs "plddt"). Normalize before lookup.
        actual = metrics.get(metric.removeprefix("min_"))
        if actual is None:
            continue
        if actual >= threshold:
            passed.append(f"{metric}: {actual:.2f} >= {threshold}")
        else:
            failed.append(f"{metric}: {actual:.2f} < {threshold}")

    evaluated = len(passed) + len(failed)
    return {
        "design_type": design_type,
        "passed": passed,
        "failed": failed,
        # Fail closed: when no threshold could be evaluated, the gate has
        # no evidence to pass on, so it must not report success.
        "is_passing": evaluated > 0 and len(failed) == 0,
        "no_metrics_evaluated": evaluated == 0,
        "thresholds": thresholds,
    }


def main() -> int:
    """Main entry point."""
    try:
        data = read_hook_input()
    except json.JSONDecodeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    if not isinstance(data, dict):
        return 0

    # Only process validation tool completions
    result = data.get("result") or {}
    if isinstance(result, dict) and result.get("isError"):
        return 0

    # Extract tool result
    text = extract_content_text(result)
    try:
        tool_result = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return 0

    # Only process validation tools. Prefer explicit payload keys; the
    # full-payload text match is a last-resort fallback for agents that do
    # not populate a tool name (an arbitrary field mentioning "boltz" must
    # not trigger the gate).
    tool_indicators = ["alphafold", "boltz", "chai", "omegafold", "esmfold", "protenix"]
    tool_name = str(data.get("tool") or data.get("tool_name") or "").lower()
    if not tool_name and isinstance(data.get("tool_input"), dict):
        tool_input = data["tool_input"]
        tool_name = str(tool_input.get("tool") or tool_input.get("tool_name") or "").lower()
    if tool_name:
        if not any(ind in tool_name for ind in tool_indicators):
            return 0
    elif not any(ind in str(data).lower() for ind in tool_indicators):
        return 0

    metrics = _extract_metrics(tool_result)
    if not metrics:
        return 0

    design_type = _detect_design_type(tool_result)
    evaluation = _evaluate_quality(metrics, design_type)

    if evaluation["is_passing"]:
        status = "✅ PASS"
        action = "Design meets quality thresholds. Proceed to Stage 4 (Filtering) or finalize."
    elif evaluation.get("no_metrics_evaluated"):
        status = "❌ FAIL"
        action = ("No evaluable metrics matched this design type's thresholds "
                  "(extracted metrics did not overlap). Failing closed: re-run "
                  "validation or check that the tool reports the gated metrics.")
    else:
        status = "❌ FAIL"
        action = "Design below thresholds. Consider: regenerate with more samples, adjust parameters, or try alternative validation tool."

    output = f"""[Quality Gate] {status} — {design_type.upper()} design

Metrics:
"""
    for p in evaluation["passed"]:
        output += f"  ✅ {p}\n"
    for f in evaluation["failed"]:
        output += f"  ❌ {f}\n"

    output += f"""
Decision: {action}

Next steps:
"""
    if evaluation["is_passing"]:
        output += """  • Add to candidate pool for experimental validation
  • Compare with other designs using analyze_alphafold3_results
  • Run additional seeds for top candidates (num_seeds=5)
"""
    else:
        output += """  • Regenerate with adjusted parameters (see auto-parameter-tuner skill)
  • Cross-validate with alternative tool (Boltz-1/Chai-1/Protenix)
  • If pLDDT is close, try more diffusion steps or longer sequences
  • Consider relaxing thresholds if this is an early screening round
"""

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
