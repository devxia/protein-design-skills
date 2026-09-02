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
    3 = Wait timed out (job still running)

`wait` returns the tracked job's exit code instead of the codes above:
143 for a cancelled job (128 + SIGTERM; see `cancel`), and 1 for a job
whose process died without recording an exit code.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.process_utils import (
    get_process_identity,
    process_group_is_alive,
    process_group_popen_kwargs,
    terminate_process_group,
)


def get_jobs_dir() -> Path:
    """Get the jobs tracking directory."""
    jobs_dir = Path.home() / ".protein-design" / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


def _read_metadata(meta_file: Path) -> Optional[dict]:
    """Read job metadata; return None for a missing or corrupt file.

    A submit that crashes midway can leave a half-written or placeholder
    file behind, so readers tolerate that the way ``list_jobs`` already
    does instead of tracebacking.
    """
    try:
        with open(meta_file, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):  # ValueError covers JSONDecodeError
        return None


def _write_metadata(meta_file: Path, metadata: dict) -> None:
    """Write job metadata atomically so readers never see a half-written file."""
    tmp_file = meta_file.with_name(meta_file.name + ".tmp")  # stays out of *.json globs
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    os.replace(tmp_file, meta_file)


def _read_exit_code(exit_file: Path) -> Optional[int]:
    """Return a complete integer marker, or ``None`` for invalid content."""
    try:
        value = exit_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not value:
        return None
    digits = value[1:] if value[0] in "+-" else value
    if not digits or any(character < "0" or character > "9" for character in digits):
        return None
    return int(value)


def _wait_for_process_group_exit(
    pid: int,
    timeout: float,
    *,
    fallback_to_process: bool = True,
) -> bool:
    """Wait until a process group is confirmed dead within ``timeout``."""
    deadline = time.monotonic() + timeout
    while True:
        alive = process_group_is_alive(
            pid,
            fallback_to_process=fallback_to_process,
        )
        if alive is False:
            return True
        if alive is None:
            return False
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.05, remaining))


def _nonnegative_timeout(value: str) -> int:
    """Argparse type for a timeout that allows zero but rejects negatives."""
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("timeout must be non-negative")
    return parsed


def generate_job_id(jobs_dir: Optional[Path] = None) -> str:
    """Generate and atomically claim a unique job ID.

    Keeps the ``<timestamp>_<counter>`` format (the timestamp prefix
    preserves chronological ordering), but instead of relying on a racy
    ``len(glob(...))`` counter, the candidate's metadata file is created
    with ``O_CREAT | O_EXCL`` to claim it — two concurrent submits in the
    same second can no longer receive the same ID and overwrite each
    other's files. The placeholder is replaced with real metadata when
    ``submit_job`` finishes writing.
    """
    jobs_dir = jobs_dir or get_jobs_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Start past the counters already used this second, then let the
    # exclusive-create claim arbitrate; retry on collision.
    counter = len(list(jobs_dir.glob(f"{timestamp}_*.json")))
    for attempt in range(counter, counter + 1000):
        job_id = f"{timestamp}_{attempt:03d}"
        try:
            fd = os.open(
                jobs_dir / f"{job_id}.json",
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            continue
        os.close(fd)
        return job_id
    raise RuntimeError("could not claim a unique job ID")


def submit_job(command: list[str], job_name: str = "", verbose: bool = False) -> str:
    """Submit a background job and return job ID."""
    jobs_dir = get_jobs_dir()
    job_id = generate_job_id(jobs_dir)
    log_dir = jobs_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"{job_id}.log"
    pid_file = jobs_dir / f"{job_id}.pid"
    meta_file = jobs_dir / f"{job_id}.json"
    exit_file = jobs_dir / f"{job_id}.exit"

    # Start process
    if verbose:
        print(f"Submitting job {job_id}: {' '.join(command)}")

    with open(log_file, "w", encoding="utf-8") as log:
        log.write(f"# Job {job_id}\n")
        log.write(f"# Command: {' '.join(command)}\n")
        log.write(f"# Started: {datetime.now().isoformat()}\n")
        log.write("# " + "=" * 60 + "\n")
        log.flush()

        # Wrap the command in a tiny Python launcher that records the real
        # exit code (both in the log and in a completion-marker file) after
        # the command finishes, so status/wait can report it truthfully
        # regardless of whether the launcher process has been reaped yet.
        # A command that cannot launch records 127 ("command not found"),
        # so the marker is always written for started jobs.
        wrapper_code = (
            "import os, subprocess, sys\n"
            "try:\n"
            "    r = subprocess.run(sys.argv[2:])\n"
            "    rc = r.returncode\n"
            "except Exception:\n"
            "    rc = 127\n"
            "tmp = sys.argv[1] + '.tmp.' + str(os.getpid())\n"
            "try:\n"
            "    with open(tmp, 'w', encoding='utf-8') as marker:\n"
            "        marker.write(str(rc))\n"
            "        marker.flush()\n"
            "    os.replace(tmp, sys.argv[1])\n"
            "finally:\n"
            "    try:\n"
            "        os.unlink(tmp)\n"
            "    except FileNotFoundError:\n"
            "        pass\n"
            "print('EXIT_CODE: ' + str(rc))\n"
            "sys.exit(rc)\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", wrapper_code, str(exit_file)] + command,
            **process_group_popen_kwargs(
                stdout=log,
                stderr=subprocess.STDOUT,
            ),
        )

    # Write PID file
    with open(pid_file, "w", encoding="utf-8") as f:
        f.write(str(process.pid))

    # Write metadata. Creation time protects later cancellation from PID reuse
    # when the current platform can obtain it; missing identity remains
    # compatible with metadata written by older versions.
    metadata = {
        "job_id": job_id,
        "job_name": job_name or command[0],
        "command": command,
        "pid": process.pid,
        "status": "running",
        "start_time": datetime.now().isoformat(),
        "log_file": str(log_file),
    }
    process_identity = get_process_identity(process.pid)
    if process_identity is not None:
        metadata["process_identity"] = process_identity
    _write_metadata(meta_file, metadata)

    if verbose:
        print(f"Job {job_id} started (PID {process.pid})")
        print(f"Log: {log_file}")

    return job_id


def get_job_status(job_id: str) -> dict:
    """Get current status of a job."""
    jobs_dir = get_jobs_dir()
    meta_file = jobs_dir / f"{job_id}.json"
    pid_file = jobs_dir / f"{job_id}.pid"
    exit_file = jobs_dir / f"{job_id}.exit"

    if not meta_file.exists():
        return {"error": f"Job {job_id} not found"}

    metadata = _read_metadata(meta_file)
    if metadata is None:
        # Corrupt or half-written metadata (e.g. from a crashed submit):
        # treat like a missing job instead of tracebacking.
        return {"error": f"Job {job_id} not found"}

    # A terminal status recorded in the metadata (a job cancelled via
    # `cancel`) stays authoritative: a dead PID must not resurrect it as
    # "completed", which `wait` would then report as success.
    if metadata.get("status") == "cancelled":
        return metadata

    # A marker is authoritative only after the launcher has atomically
    # published a complete integer. Empty or corrupt files are ignored.
    exit_code = _read_exit_code(exit_file)
    if exit_code is not None:
        metadata["exit_code"] = exit_code
        metadata["status"] = "completed"
        return metadata

    # Fallback: best-effort liveness check for jobs still running.
    pid = metadata.get("pid")
    if pid and pid_file.exists():
        alive = process_group_is_alive(pid)
        if alive is True:
            metadata["status"] = "running"
        elif alive is False:
            # The launcher writes its marker before exiting, so a dead process
            # without a valid one was killed or failed while publishing it.
            metadata["status"] = "failed"
        else:
            metadata["status"] = "unknown"
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

            # Use the same strict marker contract as get_job_status.
            exit_file = jobs_dir / f"{meta_file.stem}.exit"
            exit_code = _read_exit_code(exit_file)
            pid = metadata.get("pid")
            if metadata.get("status") == "cancelled":
                # Terminal status recorded by `cancel` stays authoritative;
                # a dead PID must not rewrite it to "completed".
                metadata["current_status"] = "cancelled"
            elif exit_code is not None:
                metadata["current_status"] = "completed"
                metadata["exit_code"] = exit_code
            elif pid:
                alive = process_group_is_alive(pid)
                if alive is True:
                    metadata["current_status"] = "running"
                elif alive is False:
                    metadata["current_status"] = "failed"
                else:
                    metadata["current_status"] = "unknown"
            else:
                metadata["current_status"] = "unknown"

            if status_filter == "all" or metadata.get("current_status") == status_filter:
                jobs.append(metadata)
        except Exception:
            continue

    return jobs


def cancel_job(job_id: str, verbose: bool = False) -> bool:
    """Cancel a running job, recording cancellation only after verified exit."""
    jobs_dir = get_jobs_dir()
    meta_file = jobs_dir / f"{job_id}.json"

    metadata = _read_metadata(meta_file)
    if metadata is None:
        print(f"ERROR: Job {job_id} not found", file=sys.stderr)
        return False

    # Never signal a job that already reached a terminal state: its PID may
    # have been recycled by an unrelated process. get_job_status resolves
    # the authoritative state (recorded terminal status / exit marker).
    current = get_job_status(job_id).get("status")
    if current in ("completed", "cancelled", "failed"):
        print(f"Job {job_id} is already {current}; nothing to cancel", file=sys.stderr)
        return True

    pid = metadata.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        print(f"ERROR: Job {job_id} has no valid PID", file=sys.stderr)
        return False

    # If submit recorded a creation-time identity, an inability to reproduce
    # it is ambiguous and must fail safe. Metadata from older versions has no
    # such field and retains the legacy PID-only cancellation path.
    if "process_identity" in metadata:
        expected_identity = metadata["process_identity"]
        current_identity = get_process_identity(pid)
        if current_identity is None:
            print(
                f"ERROR: Cannot confirm process identity for job {job_id}",
                file=sys.stderr,
            )
            return False
        if current_identity != expected_identity:
            print(
                f"ERROR: Process identity mismatch for job {job_id}",
                file=sys.stderr,
            )
            return False

    try:
        # New jobs are known process-group leaders. If their group disappears,
        # do not fall back to a possibly zombie/recycled leader PID. Legacy
        # metadata keeps the PID fallback for jobs created before isolation.
        fallback_to_process = "process_identity" not in metadata

        # First request graceful process-tree termination. Escalate only while
        # the group remains alive, then require an explicit dead result before
        # publishing cancelled metadata.
        if not terminate_process_group(pid):
            print(f"ERROR: Failed to terminate job {job_id}", file=sys.stderr)
            return False
        if not _wait_for_process_group_exit(
            pid,
            1.0,
            fallback_to_process=fallback_to_process,
        ):
            force_sent = terminate_process_group(pid, force=True)
            if not force_sent:
                # The group may have exited between the graceful-wait deadline
                # and escalation. The earlier SIGTERM was sent successfully,
                # so accept this race only when a fresh probe confirms death.
                if process_group_is_alive(
                    pid,
                    fallback_to_process=fallback_to_process,
                ) is not False:
                    print(f"ERROR: Failed to force-kill job {job_id}", file=sys.stderr)
                    return False
            elif not _wait_for_process_group_exit(
                pid,
                5.0,
                fallback_to_process=fallback_to_process,
            ):
                print(
                    f"ERROR: Job {job_id} process group is still alive or unconfirmed",
                    file=sys.stderr,
                )
                return False
    except (OSError, TypeError, ValueError):
        print(f"ERROR: Failed to cancel job {job_id}", file=sys.stderr)
        return False

    metadata["status"] = "cancelled"
    metadata["end_time"] = datetime.now().isoformat()
    _write_metadata(meta_file, metadata)

    if verbose:
        print(f"Job {job_id} cancelled")

    return True


def wait_job(job_id: str, timeout: Optional[float] = None, verbose: bool = False) -> int:
    """Wait for a job to complete.

    Returns the job's exit code on completion; 143 for a cancelled job
    (128 + SIGTERM, matching how ``cancel`` terminates it); 1 for a job
    that died without recording an exit code, or if the job does not
    exist; 3 if the wait timed out with the job still running.
    """
    start = time.monotonic()
    while True:
        status = get_job_status(job_id)
        if "error" in status:
            print(f"ERROR: {status['error']}", file=sys.stderr)
            return 1
        if status.get("status") in ("completed", "cancelled", "failed"):
            exit_code = status.get("exit_code")
            if exit_code is None:
                # A cancelled job (killed with SIGTERM -> 128 + 15) or one
                # that died without recording an exit code must never be
                # reported as success.
                exit_code = 143 if status["status"] == "cancelled" else 1
            if verbose:
                print(f"Job {job_id} finished with exit code {exit_code}")
            return exit_code

        if timeout is not None and (time.monotonic() - start) >= timeout:
            print(
                f"WARNING: Timeout waiting for job {job_id} (still running)",
                file=sys.stderr,
            )
            return 3

        time.sleep(2)


def tail_log(job_id: str, lines: int = 20) -> str:
    """Get last N lines of job log."""
    status = get_job_status(job_id)
    log_file = status.get("log_file")

    if not log_file or not Path(log_file).exists():
        return f"No log file for job {job_id}"

    try:
        # Read backwards from EOF in blocks instead of slurping the whole
        # file, so tailing a huge log stays memory-friendly.
        data = b""
        with open(log_file, "rb") as f:
            f.seek(0, os.SEEK_END)
            remaining = f.tell()
            while remaining > 0 and data.count(b"\n") <= lines:
                step = min(4096, remaining)
                remaining -= step
                f.seek(remaining)
                data = f.read(step) + data
        tail = data.decode("utf-8", errors="replace").splitlines(keepends=True)[-lines:]
        return "".join(tail)
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
    submit_parser.add_argument("run_command", nargs=argparse.REMAINDER, help="Command to run")

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
    wait_parser = subparsers.add_parser(
        "wait", help="Wait for job completion (cancelled jobs return exit code 143)"
    )
    wait_parser.add_argument("job_id", help="Job ID")
    wait_parser.add_argument(
        "--timeout", "-t", type=_nonnegative_timeout, help="Timeout in seconds"
    )
    wait_parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.command == "submit":
        run_command = args.run_command
        # argparse keeps a leading "--" in REMAINDER; strip it.
        if run_command and run_command[0] == "--":
            run_command = run_command[1:]
        if not run_command:
            print("ERROR: No command specified", file=sys.stderr)
            return 2
        job_id = submit_job(run_command, job_name=args.name, verbose=args.verbose)
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
