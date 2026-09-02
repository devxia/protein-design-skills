#!/usr/bin/env python3
"""PostToolUse hook: enforce quality gates after validation stage.

After structure prediction completes, this hook checks confidence metrics
against project-specific thresholds and provides clear pass/fail decisions
with actionable next steps — reducing manual review overhead.
"""
import json
import math
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from protein_design.utils import (
    discover_confidence_files,
    extract_content_text,
    get_hook_invoked_runner,
    get_hook_invoked_runner_arguments,
    get_hook_tool_response,
    hook_advisory_output,
    parse_confidence_json,
    read_hook_input,
)


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


def _to_float(value: Any) -> Optional[float]:
    """Coerce one finite numeric value without raising."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalise_metric(key: str, value: Any) -> Optional[float]:
    """Return a confidence metric only when it is in its valid range."""
    metric = key.lower().replace("mean_", "")
    number = _to_float(value)
    if number is None:
        return None
    if metric == "plddt" and 0.0 <= number <= 100.0:
        return number
    if metric in {"iptm", "ptm"} and 0.0 <= number <= 1.0:
        return number
    return None


def _extract_metrics(result: dict[str, Any]) -> dict[str, float]:
    """Extract confidence metrics from a safely decoded tool result."""
    metrics: dict[str, float] = {}
    if not isinstance(result, dict):
        return metrics

    # Try different result formats, accepting only mapping-shaped blocks.
    m = result.get("metrics")
    if isinstance(m, dict):
        for key in ["mean_plddt", "plddt", "iptm", "ipTM", "ptm", "pTM"]:
            value = _normalise_metric(key, m.get(key))
            if value is not None:
                metrics[key.lower().replace("mean_", "")] = value
    else:
        value = _normalise_metric("plddt", result.get("plddt"))
        if value is not None:
            metrics["plddt"] = value

        c = result.get("confidence")
        if isinstance(c, dict):
            for key in ["plddt", "iptm", "ptm"]:
                value = _normalise_metric(key, c.get(key))
                if value is not None:
                    metrics[key] = value

    if metrics:
        return metrics
    for key in ("tool_response", "result", "response", "output", "content"):
        nested = result.get(key)
        if isinstance(nested, (dict, list, str)):
            nested_metrics = _extract_metrics(nested) if isinstance(nested, dict) else {}
            if nested_metrics:
                return nested_metrics
    return metrics


def _decode_tool_response(value: Any) -> Optional[dict[str, Any]]:
    """Decode direct, wrapped, or JSON-string responses safely."""
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return None
        return _decode_tool_response(decoded) if isinstance(decoded, (dict, list)) else None

    if isinstance(value, dict):
        if value.get("isError"):
            return value
        if any(key in value for key in ("status", "metrics", "plddt", "confidence")):
            return value

        # Prefer actual response containers over generic text extraction, so
        # an outer wrapper containing JSON text is unwrapped before fallback.
        for key in ("tool_response", "result", "response", "output", "content"):
            if key not in value:
                continue
            nested = value[key]
            if nested is value:
                continue
            decoded = _decode_tool_response(nested)
            if decoded is not None:
                return decoded

        text = extract_content_text(value)
        if text:
            try:
                decoded = json.loads(text)
            except (TypeError, ValueError):
                decoded = None
            if isinstance(decoded, (dict, list)):
                return _decode_tool_response(decoded)
    elif isinstance(value, list):
        for nested in value:
            decoded = _decode_tool_response(nested)
            if decoded is not None:
                return decoded
    return None


_FAILURE_STATUSES = {
    "cancelled",
    "canceled",
    "error",
    "errored",
    "failed",
    "failure",
    "killed",
    "timed_out",
    "timeout",
}
_VALIDATION_SCRIPTS = {
    "run_alphafold3.py",
    "run_boltz.py",
    "run_chai1.py",
    "run_esmfold.py",
    "run_omegafold.py",
    "run_openfold3.py",
    "run_protenix.py",
}


def _error_flag_is_set(value: Any) -> bool:
    """Interpret common boolean-shaped error flags without treating 'false' as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes"}
    return False


def _response_is_error(value: Any) -> bool:
    """Return whether a response or nested wrapper marks an error."""
    if isinstance(value, dict):
        if _error_flag_is_set(value.get("isError")):
            return True
        status = value.get("status")
        if isinstance(status, str) and status.strip().casefold() in _FAILURE_STATUSES:
            return True
        error = value.get("error")
        if error not in (None, False, "", [], {}):
            return True
        return any(
            _response_is_error(value.get(key))
            for key in ("tool_response", "result", "response", "output", "content")
            if key in value
        )
    if isinstance(value, list):
        return any(_response_is_error(item) for item in value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return False
        return _response_is_error(decoded) if isinstance(decoded, (dict, list)) else False
    return False


def _is_validation_invocation(data: dict[str, Any]) -> bool:
    """Recognize validation only through the shared allowlisted runner parser."""
    return get_hook_invoked_runner(data) in {
        Path(script).stem for script in _VALIDATION_SCRIPTS
    }


def _output_dir_metrics(data: dict[str, Any]) -> dict[str, float]:
    """Load the first usable confidence artifact from a safe runner output dir."""
    args = get_hook_invoked_runner_arguments(data)
    output_dir = None
    for index, value in enumerate(args[:-1]):
        if value in {"--output-dir", "--out-dir", "--output", "-o"}:
            output_dir = args[index + 1]
            break
    if not output_dir:
        return {}
    try:
        files = discover_confidence_files(Path(output_dir))
    except (OSError, ValueError):
        return {}
    for path in files:
        try:
            metrics = _extract_metrics({"metrics": parse_confidence_json(path)})
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if metrics:
            return metrics
    return {}


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

    evaluated = 0
    for metric, threshold in thresholds.items():
        # Threshold keys are prefixed with "min_"; extracted metric keys are
        # not (e.g. "min_plddt" vs "plddt"). Normalize before lookup.
        metric_name = metric.removeprefix("min_")
        actual = metrics.get(metric_name)
        if actual is None:
            failed.append(f"{metric}: missing (required >= {threshold})")
            continue
        evaluated += 1
        if actual >= threshold:
            passed.append(f"{metric}: {actual:.2f} >= {threshold}")
        else:
            failed.append(f"{metric}: {actual:.2f} < {threshold}")

    return {
        "design_type": design_type,
        "passed": passed,
        "failed": failed,
        "is_passing": len(failed) == 0,
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

    # Do not scan arbitrary payload text: a recognized validation runner is
    # the sole trigger. Once recognized, the gate must always emit a decision.
    if not _is_validation_invocation(data):
        return 0

    result = get_hook_tool_response(data)
    tool_result = _decode_tool_response(result)
    if not isinstance(tool_result, dict):
        tool_result = {}
    response_failed = _response_is_error(result) or _response_is_error(tool_result)

    # Prefer metrics returned by the runner, then inspect the runner's explicit
    # output directory for canonical confidence artifacts. Both absence paths
    # fail closed below rather than silently skipping the validation run.
    metrics = {} if response_failed else _extract_metrics(tool_result)
    if not metrics:
        metrics = _output_dir_metrics(data)

    design_type = _detect_design_type(tool_result)
    evaluation = _evaluate_quality(metrics, design_type)

    if response_failed:
        evaluation["is_passing"] = False
        evaluation["failed"].append("validation runner reported an error")
        status = "❌ FAIL"
        action = "Validation runner failed; re-run it successfully before accepting this design."
    elif evaluation["is_passing"]:
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
  • Compare with other designs using scripts/run_filtering.py
  • Run additional seeds for top candidates (--num-seeds 5)
"""
    else:
        output += """  • Regenerate with adjusted parameters (see auto-parameter-tuner skill)
  • Cross-validate with alternative tool (Boltz-1/Chai-1/Protenix)
  • If pLDDT is close, try more diffusion steps or longer sequences
  • Consider relaxing thresholds if this is an early screening round
"""

    print(hook_advisory_output(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
