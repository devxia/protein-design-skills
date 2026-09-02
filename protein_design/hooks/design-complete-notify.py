#!/usr/bin/env python3
"""PostToolUse hook: send desktop notification when design jobs complete.

Triggered after tool execution completes.
Supports macOS (osascript), Linux (notify-send), and Windows (powershell).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from protein_design.utils import (
    extract_content_text, get_hook_invoked_runner, get_hook_tool_response,
    hook_advisory_output, read_hook_input, send_notification,
)
import traceback
import json
from typing import Any, Optional


def _decode_response(value: Any) -> Optional[dict[str, Any]]:
    """Decode nested response wrappers into a safe structured object."""
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return None
        return _decode_response(decoded) if isinstance(decoded, (dict, list)) else None

    if isinstance(value, dict):
        if value.get("isError"):
            return value
        recognized = {"status", "metrics", "output_path", "task_id", "tool_name", "tool"}
        if any(key in value for key in recognized):
            return value

        text = extract_content_text(value)
        if text:
            try:
                decoded = json.loads(text)
            except (TypeError, ValueError):
                decoded = None
            if isinstance(decoded, (dict, list)):
                result = _decode_response(decoded)
                if result is not None:
                    return result

        for key in ("tool_response", "result", "response", "output", "content"):
            nested = value.get(key)
            if nested is value:
                continue
            decoded = _decode_response(nested)
            if decoded is not None:
                return decoded
    elif isinstance(value, list):
        for nested in value:
            decoded = _decode_response(nested)
            if decoded is not None:
                return decoded
    return None


def _response_is_error(value: Any) -> bool:
    """Return whether a response or any nested wrapper marks an error."""
    if isinstance(value, dict):
        if bool(value.get("isError")):
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


def _find_metrics(data: Any) -> dict[str, Any]:
    """Find a metrics mapping without assuming response nesting is valid."""
    if not isinstance(data, dict):
        return {}
    metrics = data.get("metrics")
    if isinstance(metrics, dict):
        return metrics
    for key in ("tool_response", "result", "response", "output"):
        nested = data.get(key)
        found = _find_metrics(nested)
        if found:
            return found
    return {}


def extract_metrics(result_text: Any) -> dict:
    """Try to extract key metrics from tool result JSON."""
    data = result_text if isinstance(result_text, dict) else None
    if data is None:
        try:
            data = json.loads(result_text)
        except (TypeError, ValueError):
            return {}
    metrics = _find_metrics(data)
    return {
        "plddt": metrics.get("mean_plddt"),
        "iptm": metrics.get("iptm"),
        "ptm": metrics.get("ptm"),
    } if metrics else {}


def _format_metric(label: str, value: object, fmt: str) -> str:
    """Format a metric value, falling back to the raw value if non-numeric."""
    try:
        return f"{label}: {float(value):{fmt}}"  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return f"{label}: {value}"


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
    runner = get_hook_invoked_runner(data)

    # Check if this is a query_job response with completed status. The
    # standard tool_response is preferred; get_hook_tool_response preserves
    # compatibility with the legacy result field.
    response = get_hook_tool_response(data)
    result_json = _decode_response(response)
    if not isinstance(result_json, dict) or _response_is_error(response):
        return 0

    status = result_json.get("status", "")
    if status != "completed":
        return 0

    tool_name = runner or str(result_json.get("tool_name") or "protein_design")
    metrics = extract_metrics(result_json)

    title = f"✅ {tool_name} Complete"
    msg_parts = [f"Job {result_json.get('task_id', 'unknown')} finished."]

    if metrics.get("plddt") is not None:
        msg_parts.append(_format_metric("pLDDT", metrics["plddt"], ".1f"))
    if metrics.get("iptm") is not None:
        msg_parts.append(_format_metric("ipTM", metrics["iptm"], ".3f"))
    if metrics.get("ptm") is not None:
        msg_parts.append(_format_metric("pTM", metrics["ptm"], ".3f"))

    output_path = result_json.get("output_path")
    if output_path:
        msg_parts.append(f"Output: {output_path}")

    message = " | ".join(msg_parts)
    send_notification(title, message)
    print(hook_advisory_output(f"[Design Complete] {message}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
