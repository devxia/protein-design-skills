#!/usr/bin/env python3
"""PostToolUse hook: send desktop notification when design jobs complete.

Triggered after tool execution completes.
Supports macOS (osascript), Linux (notify-send), and Windows (powershell).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from protein_design.utils import send_notification
import traceback
import json


def extract_metrics(result_text: str) -> dict:
    """Try to extract key metrics from tool result JSON."""
    try:
        data = json.loads(result_text)
        metrics = data.get("result", {}).get("metrics", {})
        return {
            "plddt": metrics.get("mean_plddt"),
            "iptm": metrics.get("iptm"),
            "ptm": metrics.get("ptm"),
        }
    except Exception:
        return {}


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

    # Check if this is a query_job response with completed status
    result = data.get("result") or {}
    content = result.get("content", [{}]) if isinstance(result, dict) else [{}]
    result_text = content[0].get("text", "") if content else ""
    try:
        result_json = json.loads(result_text)
    except json.JSONDecodeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    status = result_json.get("status", "")
    if status != "completed":
        return 0

    tool_name = result_json.get("tool_name", "protein_design")
    metrics = extract_metrics(result_text)

    title = f"✅ {tool_name} Complete"
    msg_parts = [f"Job {result_json.get('task_id', 'unknown')} finished."]

    if metrics.get("plddt") is not None:
        msg_parts.append(f"pLDDT: {metrics['plddt']:.1f}")
    if metrics.get("iptm") is not None:
        msg_parts.append(f"ipTM: {metrics['iptm']:.3f}")
    if metrics.get("ptm") is not None:
        msg_parts.append(f"pTM: {metrics['ptm']:.3f}")

    if result_json.get("output_path"):
        msg_parts.append(f"Output: {result_json['output_path']}")

    message = " | ".join(msg_parts)
    send_notification(title, message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
