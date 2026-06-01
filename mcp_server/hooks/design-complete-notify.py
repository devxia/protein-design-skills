#!/usr/bin/env python3
"""PostToolUse hook: send desktop notification when design jobs complete.

Triggered after query_job returns "completed" status.
Supports macOS (osascript), Linux (notify-send), and Windows (powershell).
"""

import json
import os
import platform
import subprocess
import sys


def send_notification(title: str, message: str) -> None:
    """Send cross-platform desktop notification."""
    system = platform.system()

    if system == "Darwin":
        # macOS
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], capture_output=True, check=False)
    elif system == "Linux":
        # Linux
        subprocess.run(
            ["notify-send", title, message],
            capture_output=True,
            check=False,
        )
    elif system == "Windows":
        # Windows PowerShell
        ps_script = f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show("{message}", "{title}")'
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            check=False,
        )


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
    except Exception:
        data = {}

    # Check if this is a query_job response with completed status
    result_text = data.get("result", {}).get("content", [{}])[0].get("text", "")
    try:
        result_json = json.loads(result_text)
    except Exception:
        return 0

    status = result_json.get("status", "")
    if status != "completed":
        return 0

    tool_name = result_json.get("tool_name", "protein_design")
    metrics = extract_metrics(result_text)

    title = f"✅ {tool_name} Complete"
    msg_parts = [f"Job {result_json.get('task_id', 'unknown')} finished."]

    if metrics.get("plddt"):
        msg_parts.append(f"pLDDT: {metrics['plddt']:.1f}")
    if metrics.get("iptm"):
        msg_parts.append(f"ipTM: {metrics['iptm']:.3f}")
    if metrics.get("ptm"):
        msg_parts.append(f"pTM: {metrics['ptm']:.3f}")

    if result_json.get("output_path"):
        msg_parts.append(f"Output: {result_json['output_path']}")

    message = " | ".join(msg_parts)
    send_notification(title, message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
