#!/usr/bin/env python3
"""
Standalone lightweight job manager.
Usage:
  python scripts/job_manager.py submit -- python scripts/run_rfdiffusion.py --contig "150-150"
  python scripts/job_manager.py list
  python scripts/job_manager.py status <job_id>
  python scripts/job_manager.py cancel <job_id>
  python scripts/job_manager.py wait <job_id>

Features:
  - PID-based process tracking
  - Log file capture
  - Exit code detection
  - No daemon required

Exit codes:
    0 = Success (operation completed)
    1 = Job not found
    2 = Invalid command
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def get_jobs_dir() -> Path:
    """Get the jobs tracking directory."""
    jobs_dir = Path.home() / ".protein-design" / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


def generate_job_id() -> str:
    """Generate unique job ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Add counter for same-second jobs
    jobs_dir = get_jobs_dir()
    existing = list(jobs_dir.glob(f"{timestamp}_*.json"))
    counter = len(existing)
    return f"{timestamp}_{counter:03d}"


def submit_job(command: list[str], job_name: str = "", verbose: bool = False) -> str:
    """Submit a background job and return job ID."""
    job_id = generate_job_id()
    jobs_dir = get_jobs_dir()
    log_dir = jobs_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"{job_id}.log"
    pid_file = jobs_dir / f"{job_id}.pid"
    meta_file = jobs_dir / f"{job_id}.json"

    # Start process
    if verbose:
        print(f"Submitting job {job_id}: {' '.join(command)}")

    with open(log_file, "w", encoding="utf-8") as log:
        log.write(f"# Job {job_id}\n")
        log.write(f"# Command: {' '.join(command)}\n")
        log.write(f"# Started: {datetime.now().isoformat()}\n")
        log.write("# " + "=" * 60 + "\n")
        log.flush()

        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # Detach from parent
        )

    # Write PID file
    with open(pid_file, "w", encoding="utf-8") as f:
        f.write(str(process.pid))

    # Write metadata
    metadata = {
        "job_id": job_id,
        "job_name": job_name or command[0],
        "command": command,
        "pid": process.pid,
        "status": "running",
        "start_time": datetime.now().isoformat(),
        "log_file": str(log_file),
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    if verbose:
        print(f"Job {job_id} started (PID {process.pid})")
        print(f"Log: {log_file}")

    return job_id


def get_job_status(job_id: str) -> dict:
    """Get current status of a job."""
    jobs_dir = get_jobs_dir()
    meta_file = jobs_dir / f"{job_id}.json"
    pid_file = jobs_dir / f"{job_id}.pid"

    if not meta_file.exists():
        return {"error": f"Job {job_id} not found"}

    with open(meta_file, encoding="utf-8") as f:
        metadata = json.load(f)

    # Check if process is still running
    pid = metadata.get("pid")
    if pid and pid_file.exists():
        try:
            os.kill(pid, 0)  # Signal 0 checks if process exists
            metadata["status"] = "running"
        except ProcessLookupError:
            metadata["status"] = "completed"
            # Try to get exit code
            log_file = Path(metadata.get("log_file", ""))
            if log_file.exists():
                # Check last line for exit status
                try:
                    with open(log_file, encoding="utf-8") as f:
                        lines = f.readlines()
                        for line in reversed(lines):
                            if "EXIT_CODE:" in line:
                                metadata["exit_code"] = int(line.split(":")[1].strip())
                                break
                except Exception:
                    pass
    else:
        metadata["status"] = "unknown"

    return metadata


def list_jobs(status_filter: str = "all", verbose: bool = False) -> list[dict]:
    """List all tracked jobs."""
    jobs_dir = get_jobs_dir()
    jobs = []

    for meta_file in sorted(jobs_dir.glob("*.json")):
        if meta_file.name == "jobs.json":  # Skip aggregate file
            continue
        try:
            with open(meta_file, encoding="utf-8") as f:
                metadata = json.load(f)

            # Update status
            pid = metadata.get("pid")
            if pid:
                try:
                    os.kill(pid, 0)
                    metadata["current_status"] = "running"
                except ProcessLookupError:
                    metadata["current_status"] = "completed"

            if status_filter == "all" or metadata.get("current_status") == status_filter:
                jobs.append(metadata)
        except Exception:
            continue

    return jobs


def cancel_job(job_id: str, verbose: bool = False) -> bool:
    """Cancel a running job."""
    jobs_dir = get_jobs_dir()
    meta_file = jobs_dir / f"{job_id}.json"
    pid_file = jobs_dir / f"{job_id}.pid"

    if not meta_file.exists():
        print(f"ERROR: Job {job_id} not found", file=sys.stderr)
        return False

    with open(meta_file, encoding="utf-8") as f:
        metadata = json.load(f)

    pid = metadata.get("pid")
    if not pid:
        print(f"ERROR: Job {job_id} has no PID", file=sys.stderr)
        return False

    try:
        # Kill entire process group
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        time.sleep(1)
        # Force kill if still running
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass

        # Update metadata
        metadata["status"] = "cancelled"
        metadata["end_time"] = datetime.now().isoformat()
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        if verbose:
            print(f"Job {job_id} cancelled")

        return True

    except ProcessLookupError:
        print(f"WARNING: Job {job_id} process already exited", file=sys.stderr)
        return True
    except PermissionError:
        print(f"ERROR: Permission denied to cancel job {job_id}", file=sys.stderr)
        return False


def wait_job(job_id: str, timeout: int | None = None, verbose: bool = False) -> int:
    """Wait for a job to complete."""
    start = time.time()
    while True:
        status = get_job_status(job_id)
        if status.get("status") in ("completed", "cancelled"):
            exit_code = status.get("exit_code", 0)
            if verbose:
                print(f"Job {job_id} finished with exit code {exit_code}")
            return exit_code

        if timeout and (time.time() - start) > timeout:
            print(f"WARNING: Timeout waiting for job {job_id}", file=sys.stderr)
            return -1

        time.sleep(2)


def tail_log(job_id: str, lines: int = 20) -> str:
    """Get last N lines of job log."""
    status = get_job_status(job_id)
    log_file = status.get("log_file")

    if not log_file or not Path(log_file).exists():
        return f"No log file for job {job_id}"

    try:
        with open(log_file, encoding="utf-8") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading log: {e}"


def print_job_table(jobs: list[dict]) -> None:
    """Print jobs in table format."""
    if not jobs:
        print("No jobs found.")
        return

    print(f"\n{'Job ID':<20}{'Name':<20}{'Status':<12}{'PID':<10}{'Started'}")
    print("-" * 80)
    for job in jobs:
        job_id = job.get("job_id", "unknown")
        name = job.get("job_name", "unknown")[:18]
        status = job.get("current_status", job.get("status", "unknown"))
        pid = str(job.get("pid", "-"))
        started = job.get("start_time", "-")
        if started != "-":
            started = started.split("T")[1][:8]  # HH:MM:SS

        print(f"{job_id:<20}{name:<20}{status:<12}{pid:<10}{started}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lightweight job manager — process tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Submit a job
  python job_manager.py submit -- python scripts/run_rfdiffusion.py --contig "150-150" -n 50

  # List all jobs
  python job_manager.py list

  # Check status
  python job_manager.py status 20250611_143022_000

  # Tail log
  python job_manager.py tail 20250611_143022_000 --lines 50

  # Cancel a job
  python job_manager.py cancel 20250611_143022_000

  # Wait for completion
  python job_manager.py wait 20250611_143022_000 --timeout 3600
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Submit
    submit_parser = subparsers.add_parser("submit", help="Submit a background job")
    submit_parser.add_argument("--name", "-n", help="Job name")
    submit_parser.add_argument("--verbose", "-v", action="store_true")
    submit_parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run")

    # List
    list_parser = subparsers.add_parser("list", help="List all jobs")
    list_parser.add_argument("--status", choices=["all", "running", "completed"], default="all")
    list_parser.add_argument("--verbose", "-v", action="store_true")

    # Status
    status_parser = subparsers.add_parser("status", help="Get job status")
    status_parser.add_argument("job_id", help="Job ID")
    status_parser.add_argument("--verbose", "-v", action="store_true")

    # Tail
    tail_parser = subparsers.add_parser("tail", help="Tail job log")
    tail_parser.add_argument("job_id", help="Job ID")
    tail_parser.add_argument("--lines", "-n", type=int, default=20)

    # Cancel
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a job")
    cancel_parser.add_argument("job_id", help="Job ID")
    cancel_parser.add_argument("--verbose", "-v", action="store_true")

    # Wait
    wait_parser = subparsers.add_parser("wait", help="Wait for job completion")
    wait_parser.add_argument("job_id", help="Job ID")
    wait_parser.add_argument("--timeout", "-t", type=int, help="Timeout in seconds")
    wait_parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.command == "submit":
        if not args.command or args.command[0] == "--":
            print("ERROR: No command specified", file=sys.stderr)
            return 2
        # Remove leading "--" if present
        cmd = args.command[1:] if args.command[0] == "--" else args.command
        job_id = submit_job(cmd, job_name=args.name, verbose=args.verbose)
        print(job_id)
        return 0

    elif args.command == "list":
        jobs = list_jobs(status_filter=args.status, verbose=args.verbose)
        print_job_table(jobs)
        return 0

    elif args.command == "status":
        status = get_job_status(args.job_id)
        if "error" in status:
            print(status["error"], file=sys.stderr)
            return 1
        print(json.dumps(status, indent=2))
        return 0

    elif args.command == "tail":
        output = tail_log(args.job_id, lines=args.lines)
        print(output)
        return 0

    elif args.command == "cancel":
        success = cancel_job(args.job_id, verbose=args.verbose)
        return 0 if success else 1

    elif args.command == "wait":
        return wait_job(args.job_id, timeout=args.timeout, verbose=args.verbose)

    else:
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(main())
