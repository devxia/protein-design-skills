#!/usr/bin/env python3
"""Notification hook: alert when background tasks complete/fail.

Supports macOS, Linux, and Windows desktop notifications.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from protein_design.utils import send_notification
import traceback
import json


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
