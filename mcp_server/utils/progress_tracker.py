"""Progress tracking with file-system monitoring + historical ETA.

Combines two signals:
  A. File-system monitoring: count completed output files
  C. Historical ETA: estimate total runtime from past executions

The progress is the maximum of the two signals, so that:
  - If files are generated quickly, progress reflects actual completion
  - If files lag behind (e.g., I/O bottleneck), time-based progress prevents
    the UI from appearing stuck.

Historical runtimes are stored in ~/.kimi-protein-design/history.jsonl
as newline-delimited JSON records.
"""

import glob
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

HISTORY_PATH = Path.home() / ".kimi-protein-design" / "history.jsonl"

# Default runtime estimates (seconds per item) when no history exists.
# These are conservative over-estimates.
DEFAULT_ESTIMATES: dict[str, dict[str, float]] = {
    "rfdiffusion": {
        "per_item": 45.0,          # ~45s per design on A100
        "overhead": 10.0,          # startup / model load
    },
    "proteinmpnn": {
        "per_item": 8.0,           # ~8s per sequence
        "overhead": 5.0,
    },
    "alphafold3": {
        "per_item": 180.0,         # ~3 min per sample with MSA
        "overhead": 60.0,          # data pipeline overhead
        "per_item_no_msa": 30.0,   # ~30s per sample without MSA
    },
}


def _load_history(tool_name: str) -> list[dict[str, Any]]:
    """Load historical runtime records for a tool."""
    records = []
    if not HISTORY_PATH.exists():
        return records
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("tool") == tool_name:
                        records.append(rec)
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        logger.warning("Failed to load history: %s", exc)
    return records


def estimate_runtime(
    tool_name: str,
    num_items: int,
    with_msa: bool = True,
) -> float:
    """Estimate total runtime in seconds based on history or defaults.

    Args:
        tool_name: One of "rfdiffusion", "proteinmpnn", "alphafold3".
        num_items: Number of items to process (designs, sequences, samples).
        with_msa: For AlphaFold3, whether MSA pipeline is enabled.

    Returns:
        Estimated total runtime in seconds (minimum 30s).
    """
    history = _load_history(tool_name)
    defaults = DEFAULT_ESTIMATES.get(tool_name, {"per_item": 60.0, "overhead": 10.0})

    if history:
        # Use median of last 10 runs for robustness
        recent = history[-10:]
        durations = [r["duration_seconds"] / max(r["num_items"], 1) for r in recent]
        durations.sort()
        median_per_item = durations[len(durations) // 2]
        per_item = median_per_item
        overhead = 0  # historical durations already include overhead
        logger.info(
            "Using historical estimate for %s: %.1fs/item (from %d past runs)",
            tool_name, per_item, len(recent),
        )
    else:
        per_item = defaults["per_item"]
        overhead = defaults.get("overhead", 0)
        if tool_name == "alphafold3" and not with_msa:
            per_item = defaults.get("per_item_no_msa", per_item)
        logger.info(
            "Using default estimate for %s: %.1fs/item + %.1fs overhead",
            tool_name, per_item, overhead,
        )

    total = overhead + num_items * per_item
    return max(total, 30.0)


def save_runtime_log(
    tool_name: str,
    num_items: int,
    duration_seconds: float,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a completed run for future ETA estimation.

    Args:
        tool_name: Tool identifier.
        num_items: Number of items processed.
        duration_seconds: Actual wall-clock duration.
        metadata: Optional extra info (GPU type, protein size, etc.).
    """
    record = {
        "tool": tool_name,
        "num_items": num_items,
        "duration_seconds": round(duration_seconds, 2),
        "timestamp": time.time(),
        "metadata": metadata or {},
    }
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as exc:
        logger.warning("Failed to save runtime history: %s", exc)


class FileProgressTracker:
    """Tracks progress by monitoring output files + ETA.

    Spawns a background thread that polls the filesystem every few seconds
    and calls the progress_callback with the best available progress estimate.
    """

    def __init__(
        self,
        tool_name: str,
        num_expected: int,
        progress_callback: Callable[[int], None],
        output_dir: str,
        file_pattern: str,
        start_time: float | None = None,
        estimated_total_seconds: float | None = None,
        poll_interval: float = 5.0,
    ):
        """Initialize tracker.

        Args:
            tool_name: Tool identifier for history lookup.
            num_expected: Total number of expected output files.
            progress_callback: Function(progress: int) to call.
            output_dir: Directory to watch for files.
            file_pattern: Glob pattern for completed files (e.g. "*.pdb").
            start_time: Process start timestamp. Defaults to now.
            estimated_total_seconds: Pre-computed ETA. If None, auto-estimated.
            poll_interval: Seconds between filesystem polls.
        """
        self.tool_name = tool_name
        self.num_expected = max(num_expected, 1)
        self.progress_callback = progress_callback
        self.output_dir = output_dir
        self.file_pattern = file_pattern
        self.start_time = start_time or time.time()
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        if estimated_total_seconds is None:
            self.estimated_total = estimate_runtime(tool_name, num_expected)
        else:
            self.estimated_total = estimated_total_seconds

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Progress tracker already started for %s", self.tool_name)
            return
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(
            "Progress tracker started for %s: watching %s/%s, ETA %.0fs",
            self.tool_name,
            self.output_dir,
            self.file_pattern,
            self.estimated_total,
        )

    def stop(self) -> None:
        """Signal the polling thread to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.poll_interval + 1)

    def _poll_loop(self) -> None:
        """Background loop: poll files and update progress."""
        while not self._stop_event.is_set():
            progress = self._compute_progress()
            try:
                self.progress_callback(progress)
            except Exception as exc:
                logger.warning("Progress callback failed: %s", exc)

            if progress >= 95:
                break
            self._stop_event.wait(self.poll_interval)

    def _compute_progress(self) -> int:
        """Compute best progress estimate (0-100).

        Combines file-based and time-based progress. Uses the more
        optimistic signal, but caps at 95% until explicitly completed.
        Also checks for tool-specific progress markers (log lines, etc.).
        """
        # A. File-based progress
        file_progress = 0.0
        try:
            if os.path.exists(self.output_dir):
                pattern = os.path.join(self.output_dir, self.file_pattern)
                matched = glob.glob(pattern)
                # Also check for recursive patterns (e.g., */*_model.cif)
                if "**" in self.file_pattern or "/" in self.file_pattern:
                    matched = glob.glob(pattern, recursive=True)
                file_progress = len(matched) / self.num_expected * 100
        except Exception:
            file_progress = 0.0

        # B. Log-based progress markers (e.g., "step X/Y" in stdout log)
        log_progress = 0.0
        try:
            stdout_log = os.path.join(self.output_dir, f"{self.tool_name}_stdout.log")
            if os.path.exists(stdout_log):
                with open(stdout_log, "rb") as f:
                    # Seek to the last 8KB to avoid reading entire large log files
                    f.seek(0, 2)  # end of file
                    fsize = f.tell()
                    f.seek(max(0, fsize - 8192))
                    content = f.read().decode("utf-8", errors="ignore")
                # Check for common progress patterns
                if "step" in content.lower():
                    steps = re.findall(r"[Ss]tep\s+(\d+)/(\d+)", content)
                    if steps:
                        last_step, total_steps = steps[-1]
                        log_progress = int(last_step) / int(total_steps) * 100
        except Exception:
            log_progress = 0.0

        # C. Time-based progress
        elapsed = time.time() - self.start_time
        time_progress = elapsed / self.estimated_total * 100

        # Combine: take the most optimistic signal, cap at 95%
        best = max(file_progress, time_progress, log_progress)
        return min(int(best), 95)


def track_progress(
    tool_name: str,
    num_expected: int,
    progress_callback: Callable[[int], None],
    output_dir: str,
    file_pattern: str,
    estimated_total_seconds: float | None = None,
    with_msa: bool = True,
) -> FileProgressTracker:
    """Convenience factory: create and start a FileProgressTracker.

    Args:
        tool_name: Tool identifier.
        num_expected: Expected number of output files.
        progress_callback: Progress callback function.
        output_dir: Directory to monitor.
        file_pattern: Glob pattern for output files.
        estimated_total_seconds: Optional pre-computed ETA.
        with_msa: For AlphaFold3 ETA estimation.

    Returns:
        Started FileProgressTracker instance. Call .stop() when done.
    """
    if estimated_total_seconds is None:
        estimated_total_seconds = estimate_runtime(tool_name, num_expected, with_msa=with_msa)

    tracker = FileProgressTracker(
        tool_name=tool_name,
        num_expected=num_expected,
        progress_callback=progress_callback,
        output_dir=output_dir,
        file_pattern=file_pattern,
        estimated_total_seconds=estimated_total_seconds,
    )
    tracker.start()
    return tracker
