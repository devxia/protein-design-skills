#!/usr/bin/env python3
"""
Standalone AlphaFold3 runner.

Usage: python scripts/run_alphafold3.py (--json input.json | --input-dir inputs/) --output-dir outputs/af3/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = AlphaFold3 not installed / not found (argparse usage errors also exit 2)
    3 = Execution error
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history
from protein_design.conda_utils import (
    build_tool_command,
    resolve_configured_path,
    resolve_wrapper_script,
)
from protein_design.process_utils import run_process

import argparse
import json
import re
import shlex
import subprocess
import time
from textwrap import dedent


def _probe_conda_alphafold3_script(env):
    """Return AlphaFold3's real ``run_alphafold.py`` path in ``env``."""
    probe = """
import pathlib
import sys

candidates = []
try:
    import alphafold3
except (ImportError, AttributeError):
    pass
else:
    package = pathlib.Path(alphafold3.__file__).resolve().parent
    candidates.extend([
        package.parent / "run_alphafold.py",
        package / "run_alphafold.py",
        package.parent.parent / "run_alphafold.py",
    ])

prefix = pathlib.Path(sys.prefix)
candidates.extend([
    prefix / "run_alphafold.py",
    prefix / "bin" / "run_alphafold.py",
])
print(next((str(path) for path in candidates if path.is_file()), ""))
"""
    try:
        result = subprocess.run(
            ["conda", "run", "-n", env, "python", "-c", dedent(probe)],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        script = line.strip()
        if script:
            return script
    return None


def find_alphafold3(config):
    """Locate AlphaFold3's executable ``run_alphafold.py`` entry point."""
    # 1. Configured path (alphafold3_path key, with legacy alphafold_path
    # fallback).  A configured checkout directory is resolved to its standard
    # run_alphafold.py entry point rather than being passed as an executable.
    for configured_value in (
        config.get("alphafold3_path"),
        config.get("alphafold_path"),
    ):
        configured = resolve_configured_path(configured_value, ["run_alphafold.py"])
        if configured:
            return configured

    # 2. Common locations
    common_paths = [
        Path.home() / "alphafold3" / "run_alphafold.py",
        Path.home() / "AlphaFold3" / "run_alphafold.py",
        Path.home() / "alphafold" / "run_alphafold.py",
        Path("/opt/alphafold3/run_alphafold.py"),
        Path("/usr/local/alphafold3/run_alphafold.py"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    # 3. Conda environments.  AlphaFold3 does not provide a reliable
    # ``python -m alphafold3`` entry point, so only return a command after the
    # actual run_alphafold.py file has been located inside the environment.
    for env in ("alphafold3", "alphafold", "protein-design"):
        script = _probe_conda_alphafold3_script(env)
        if script:
            # build_tool_command() tokenizes conda commands with shlex.split().
            # Serialize the discovered argv with shlex.join() so paths with
            # spaces or Windows backslashes round-trip as one script argument.
            return shlex.join(["conda", "run", "-n", env, "python", script])

    return None


def find_db_dir(config):
    """Find AlphaFold3 databases directory."""
    # 1. Configured path
    if config.get("db_dir"):
        path = Path(config["db_dir"])
        if path.exists():
            return str(path)

    # 2. Common locations
    common_paths = [
        Path.home() / "public_databases",
        Path("/data/public_databases"),
        Path("/opt/public_databases"),
        Path("/usr/local/public_databases"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    return None


def _set_model_seeds(json_path, num_seeds, output_path):
    """Write a seed-expanded copy of the input JSON, leaving the original untouched.

    AlphaFold3 controls sampling through the input JSON's ``modelSeeds`` field
    rather than CLI flags. The augmented JSON is written to ``output_path``
    (parent directories are created); the user's original input file is never
    modified, so re-running with different seeds cannot corrupt a curated input.

    Returns:
        Path to the augmented JSON copy.
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    data["modelSeeds"] = list(range(1, num_seeds + 1))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return output_path


def run_alphafold3(json_path, output_dir, db_dir=None, run_data_pipeline=True,
                   num_seeds=1, verbose=False):
    """Run AlphaFold3 with given parameters."""
    config = get_config("alphafold3")
    alphafold_script = find_alphafold3(config)

    if not alphafold_script:
        print("ERROR: AlphaFold3 not found. Install from: https://github.com/google-deepmind/alphafold3",
              file=sys.stderr)
        return 2

    if not Path(json_path).exists():
        print(f"ERROR: Input JSON not found: {json_path}", file=sys.stderr)
        return 1

    # AlphaFold3 controls seeds via the input JSON's modelSeeds field.
    # Expand into a copy inside the output directory; never mutate the input.
    if num_seeds is not None and num_seeds < 1:
        print(f"NOTE: --num-seeds {num_seeds} is ignored; using the modelSeeds "
              "already defined in the input JSON.")
    if num_seeds and num_seeds > 1:
        seeds_json = Path(output_dir) / f"{Path(json_path).stem}.seeds{num_seeds}.json"
        json_path = str(_set_model_seeds(json_path, num_seeds, seeds_json))
        if verbose:
            print(f"Wrote seed-expanded input JSON: {json_path}")

    # Create output directory
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Find databases if not provided
    if run_data_pipeline and not db_dir:
        db_dir = find_db_dir(config)
        if not db_dir:
            print("WARNING: AlphaFold3 databases not found. Running without MSA (less accurate).", file=sys.stderr)
            print("Set ALPHAFOLD_DB_DIR or configure with configure_db_dir().", file=sys.stderr)
            run_data_pipeline = False

    # Build command
    wrapper = resolve_wrapper_script(config, "alphafold3")
    cmd = build_tool_command(alphafold_script, wrapper_script=wrapper)

    cmd.extend([
        "--json_path", json_path,
        "--output_dir", output_dir,
    ])

    if db_dir and run_data_pipeline:
        cmd.extend(["--db_dir", db_dir])
    else:
        if db_dir:
            print(f"NOTE: --db-dir '{db_dir}' is ignored because --no-msa "
                  "disables the data pipeline; running without MSA.")
        cmd.append("--run_data_pipeline=false")

    if verbose:
        print(f"Running: {' '.join(cmd)}")
        if db_dir:
            print(f"Using databases: {db_dir}")
        else:
            print("Running without MSA (no databases)")

    start_time = time.time()
    try:
        result = run_process(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200  # 2 hours max
        )
        runtime = time.time() - start_time

        if verbose and result.stdout:
            print(result.stdout[-2000:])

        if result.returncode != 0:
            print(f"ERROR: AlphaFold3 failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history("alphafold3", {"json": json_path}, runtime, False,
                        config["output_dir"])
            return 3

        log_history("alphafold3", {"json": json_path}, runtime, True,
                    config["output_dir"])

        if verbose:
            print(f"SUCCESS: AlphaFold3 completed in {runtime:.1f}s")
            print(f"Output: {output_dir}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: AlphaFold3 timed out (>2 hours)", file=sys.stderr)
        log_history("alphafold3", {"json": json_path}, 7200, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("alphafold3", {"json": json_path}, time.time() - start_time, False,
                    config["output_dir"])
        return 3


def _safe_unique_basename(json_path, used_names):
    """Create a deterministic, filesystem-safe output directory basename."""
    raw_name = Path(json_path).stem
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    safe_name = safe_name or "input"

    candidate = safe_name
    suffix = 2
    while candidate in used_names:
        candidate = f"{safe_name}_{suffix}"
        suffix += 1
    used_names.add(candidate)
    return candidate


def run_alphafold3_batch(input_dir, output_dir, db_dir=None,
                         run_data_pipeline=True, num_seeds=1, verbose=False):
    """Run AlphaFold3 once for every JSON file in ``input_dir``.

    Input files are processed in stable filename order.  Each input receives a
    separate output subdirectory named from its sanitized basename; collisions
    are resolved with deterministic numeric suffixes.  All files are
    attempted even when an earlier task fails, and the first non-zero status is
    returned after the batch completes.
    """
    input_path = Path(input_dir)
    if not input_path.is_dir():
        print(f"ERROR: Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    json_files = sorted(input_path.glob("*.json"), key=lambda path: path.name)
    json_files = [path for path in json_files if path.is_file()]
    if not json_files:
        print(f"ERROR: No JSON input files found in: {input_dir}", file=sys.stderr)
        return 1

    batch_output = Path(output_dir)
    batch_output.mkdir(parents=True, exist_ok=True)
    used_names = set()
    first_failure = 0

    for json_file in json_files:
        task_output = batch_output / _safe_unique_basename(json_file, used_names)
        task_output.mkdir(parents=True, exist_ok=True)
        if verbose:
            print(f"Batch task: {json_file} -> {task_output}")

        result = run_alphafold3(
            json_path=str(json_file),
            output_dir=str(task_output),
            db_dir=db_dir,
            run_data_pipeline=run_data_pipeline,
            num_seeds=num_seeds,
            verbose=verbose,
        )
        if result != 0 and first_failure == 0:
            first_failure = result if isinstance(result, int) and result > 0 else 1

    return first_failure


def build_parser():
    """Build the AlphaFold3 command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run AlphaFold3 — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard prediction with MSA
  python run_alphafold3.py --json design.json --output-dir outputs/af3/

  # Fast prediction without MSA
  python run_alphafold3.py --json design.json --output-dir outputs/af3/ --no-msa

  # Multiple seeds for confidence
  python run_alphafold3.py --json design.json --output-dir outputs/af3/ --num-seeds 5

  # Batch prediction
  python run_alphafold3.py --input-dir inputs/af3/ --output-dir outputs/af3/

  # With custom database path
  python run_alphafold3.py --json design.json --output-dir outputs/af3/ --db-dir /path/to/databases
        """
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--json", "-j",
                             help="AlphaFold3 JSON input file")
    input_group.add_argument("--input-dir",
                             help="Directory containing AlphaFold3 JSON inputs")
    parser.add_argument("--output-dir", "--out-dir", "-o", required=True,
                        help="Output directory")
    parser.add_argument("--db-dir", "-d",
                        help="Path to AlphaFold3 databases (~2.6TB)")
    parser.add_argument("--no-msa", action="store_true",
                        help="Skip MSA search (faster, less accurate)")
    parser.add_argument("--num-seeds", type=int, default=1,
                        help="Number of random seeds; sets modelSeeds in the input JSON (default: 1)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")
    return parser


def main():
    args = build_parser().parse_args()

    if args.input_dir:
        return run_alphafold3_batch(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            db_dir=args.db_dir,
            run_data_pipeline=not args.no_msa,
            num_seeds=args.num_seeds,
            verbose=args.verbose,
        )

    return run_alphafold3(
        json_path=args.json,
        output_dir=args.output_dir,
        db_dir=args.db_dir,
        run_data_pipeline=not args.no_msa,
        num_seeds=args.num_seeds,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
