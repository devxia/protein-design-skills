#!/usr/bin/env python3
"""Notification hook: alert when background tasks complete/fail.

Supports macOS, Linux, and Windows desktop notifications.
"""

import json
import platform
import subprocess
import sys


def send_notification(title: str, message: str) -> None:
    """Send cross-platform desktop notification."""
    system = platform.system()

    if system == "Darwin":
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], capture_output=True, check=False)
    elif system == "Linux":
        subprocess.run(
            ["notify-send", title, message],
            capture_output=True,
            check=False,
        )
    elif system == "Windows":
        ps_script = f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show("{message}", "{title}")'
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            check=False,
        )


def main() -> int:
    """Main entry point."""
    try:
        input_data = sys.stdin.read()
        data = json.loads(input_data) if input_data.strip() else {}
    except Exception:
        data = {}

    event = data.get("event", "")
    task_id = data.get("task_id", "unknown")

    if "completed" in event:
        title = "✅ Background Task Complete"
        message = f"Task {task_id} completed successfully."
    elif "failed" in event:
        title = "❌ Background Task Failed"
        message = f"Task {task_id} failed. Check logs for details."
    elif "killed" in event:
        title = "⚠️ Background Task Killed"
        message = f"Task {task_id} was terminated."
    else:
        return 0

    send_notification(title, message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
