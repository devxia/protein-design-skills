"""Asynchronous job management for protein design tools.

Core module that manages long-running computational tasks via a thread pool.
Supports progress tracking, timeouts, and automatic cleanup.
"""

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job lifecycle states."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a single computational job."""

    task_id: str
    tool_name: str
    params: dict[str, Any]
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0  # 0-100
    output_path: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    future: Optional[Future] = None
    process: Optional[Any] = None  # subprocess.Popen handle for cancellation


class JobManager:
    """Manages async job execution with progress tracking.

    Uses a thread pool for concurrent execution. Each tool runs in its own
    thread to avoid blocking the MCP server event loop.
    """

    def __init__(self, max_workers: int = 4, timeout: int = 3600):
        """Initialize job manager.

        Args:
            max_workers: Maximum concurrent threads in the pool.
            timeout: Default timeout in seconds for job completion.
        """
        self.max_workers = max_workers
        self.timeout = timeout
        self._jobs: dict[str, Job] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._cleanup_interval = 3600  # 1 hour

        # Start background cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def submit_job(
        self,
        tool_name: str,
        params: dict[str, Any],
        execute_fn: Callable[[dict[str, Any], Callable[[int], None]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Submit a new job for async execution.

        Args:
            tool_name: Name of the tool to execute.
            params: Tool parameters.
            execute_fn: Function that performs the actual computation.
                        Receives (params, progress_callback) -> result dict.

        Returns:
            Dict with task_id and initial status.
        """
        task_id = f"{tool_name}_{uuid.uuid4().hex[:8]}"
        job = Job(task_id=task_id, tool_name=tool_name, params=params)

        with self._lock:
            self._jobs[task_id] = job

        def progress_callback(value: int) -> None:
            """Update job progress (0-100)."""
            with self._lock:
                if task_id in self._jobs:
                    self._jobs[task_id].progress = max(0, min(100, value))

        def run_job() -> dict[str, Any]:
            """Execute the tool function."""
            with self._lock:
                if task_id not in self._jobs:
                    return {"error": "Job was removed before execution"}
                job = self._jobs[task_id]
                job.status = JobStatus.RUNNING
                job.started_at = time.time()

            try:
                result = execute_fn(params, progress_callback)
                with self._lock:
                    job.status = JobStatus.COMPLETED
                    job.progress = 100
                    job.result = result
                    job.output_path = result.get("output_dir") or result.get("output_path")
                    job.completed_at = time.time()
                return result
            except Exception as exc:
                error_msg = str(exc)
                logger.exception("Job %s failed: %s", task_id, error_msg)
                with self._lock:
                    job.status = JobStatus.FAILED
                    job.error = error_msg
                    job.completed_at = time.time()
                raise

        future = self._executor.submit(run_job)
        with self._lock:
            job.future = future

        logger.info("Submitted job %s for tool %s", task_id, tool_name)
        return {
            "task_id": task_id,
            "status": JobStatus.QUEUED.value,
            "message": f"Job submitted. Use query_job with task_id='{task_id}' to check status.",
        }

    def query_job(self, task_id: str) -> dict[str, Any]:
        """Query the status of a job.

        Args:
            task_id: The task ID returned by submit_job.

        Returns:
            Dict with current status, progress, and results/error.
        """
        with self._lock:
            job = self._jobs.get(task_id)

        if not job:
            return {
                "task_id": task_id,
                "status": "not_found",
                "error": f"No job found with task_id={task_id}",
            }

        response: dict[str, Any] = {
            "task_id": job.task_id,
            "status": job.status.value,
            "tool_name": job.tool_name,
            "progress": job.progress,
            "created_at": job.created_at,
        }

        if job.started_at:
            response["started_at"] = job.started_at
            if job.status in (JobStatus.RUNNING,):
                response["elapsed_seconds"] = round(time.time() - job.started_at, 1)

        if job.completed_at:
            response["completed_at"] = job.completed_at
            if job.started_at:
                response["duration_seconds"] = round(job.completed_at - job.started_at, 1)

        if job.output_path:
            response["output_path"] = job.output_path

        if job.result:
            response["result"] = job.result

        if job.error:
            response["error"] = job.error

        return response

    def cancel_job(self, task_id: str) -> dict[str, Any]:
        """Request cancellation of a running job.

        Attempts to terminate the subprocess (if tracked) and cleans up
        partial output files to avoid stale data on restart.

        Args:
            task_id: The task ID to cancel.

        Returns:
            Dict with cancellation status.
        """
        with self._lock:
            job = self._jobs.get(task_id)

        if not job:
            return {
                "task_id": task_id,
                "status": "not_found",
                "error": f"No job found with task_id={task_id}",
            }

        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return {
                "task_id": task_id,
                "status": job.status.value,
                "message": f"Job already in terminal state: {job.status.value}",
            }

        with self._lock:
            status = job.status
            process = job.process
            future = job.future
            params = job.params

        # Terminate subprocess if we have a handle
        if process is not None:
            try:
                process.terminate()
                # Give it a few seconds to exit gracefully
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
            except Exception as exc:
                logger.warning("Failed to terminate process for job %s: %s", task_id, exc)

        if future and not future.done():
            future.cancel()

        # Clean up partial outputs
        cleanup_msg = ""
        output_dir = params.get("output_dir") or params.get("output_prefix")
        if output_dir:
            try:
                # If output_prefix is a file prefix, get its directory
                if os.path.isfile(output_dir) or "." in os.path.basename(output_dir):
                    cleanup_dir = os.path.dirname(output_dir) or "."
                else:
                    cleanup_dir = output_dir

                # Remove known incomplete markers/files
                removed = 0
                for root, _dirs, files in os.walk(cleanup_dir):
                    for f in files:
                        if f.endswith((".tmp", ".incomplete", "_partial.pdb")):
                            os.remove(os.path.join(root, f))
                            removed += 1
                if removed:
                    cleanup_msg = f" Cleaned up {removed} partial files."
            except Exception as exc:
                logger.warning("Cleanup failed for job %s: %s", task_id, exc)

        with self._lock:
            job.status = JobStatus.CANCELLED
            job.completed_at = time.time()

        return {
            "task_id": task_id,
            "status": JobStatus.CANCELLED.value,
            "message": f"Job cancellation requested.{cleanup_msg}",
        }

    def list_jobs(self) -> dict[str, Any]:
        """List all jobs and their statuses.

        Returns:
            Dict with list of jobs.
        """
        with self._lock:
            jobs = [
                {
                    "task_id": j.task_id,
                    "tool_name": j.tool_name,
                    "status": j.status.value,
                    "progress": j.progress,
                }
                for j in self._jobs.values()
            ]
        return {"jobs": jobs, "total": len(jobs)}

    def _cleanup_loop(self) -> None:
        """Background thread to remove old completed/failed jobs."""
        while True:
            time.sleep(self._cleanup_interval)
            self._cleanup_old_jobs()

    def _cleanup_old_jobs(self) -> None:
        """Remove completed/failed jobs older than cleanup_interval."""
        now = time.time()
        to_remove = []

        with self._lock:
            for task_id, job in self._jobs.items():
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                    if job.completed_at and (now - job.completed_at) > self._cleanup_interval:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self._jobs[task_id]

        if to_remove:
            logger.info("Cleaned up %d old jobs", len(to_remove))

    def shutdown(self) -> None:
        """Gracefully shutdown the executor."""
        self._executor.shutdown(wait=True)


# Global job manager instance
JOB_MANAGER = JobManager()
