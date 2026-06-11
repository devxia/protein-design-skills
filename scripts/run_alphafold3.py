#!/usr/bin/env python3
"""
Standalone AlphaFold3 runner.

Usage: python scripts/run_alphafold3.py --json input.json --output-dir outputs/af3/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = AlphaFold3 not installed / not found
    3 = Execution error
    4 = Invalid arguments
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def get_config():
    """Read protein-design config from YAML or return defaults."""
    config_paths = [
        Path.home() / ".protein-design" / "config.yaml",
        Path.home() / ".kimi-protein-design" / "config.yaml",
    ]
    config = {
        "output_dir": os.environ.get("PROTEIN_DESIGN_OUTPUT_DIR", "/tmp/protein-design"),
        "alphafold_path": os.environ.get("ALPHAFOLD_PATH", ""),
        "db_dir": os.environ.get("ALPHAFOLD_DB_DIR", ""),
    }
    for path in config_paths:
        if path.exists():
            try:
                import yaml
                with open(path) as f:
                    file_config = yaml.safe_load(f) or {}
                config.update(file_config)
            except ImportError:
                pass
            break
    return config


def log_history(tool_name, params, runtime, success, output_dir):
    """Append execution record to history.jsonl for ETA estimation."""
    history_file = Path.home() / ".protein-design" / "history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "tool": tool_name,
        "params": params,
        "runtime": runtime,
        "success": success,
        "timestamp": datetime.now().isoformat(),
    }
    with open(history_file, "a") as f:
        f.write(json.dumps(record) + "\n")


def find_alphafold3(config):
    """Locate AlphaFold3 installation."""
    # 1. Configured path
    if config.get("alphafold_path"):
        path = Path(config["alphafold_path"])
        if path.exists():
            return str(path)

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

    # 3. Conda environments
    conda_envs = ["alphafold3", "alphafold", "protein-design"]
    for env in conda_envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env, "python", "-c",
                 "import alphafold3; print(alphafold3.__file__)"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return f"conda run -n {env} python -m alphafold3"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

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


def run_alphafold3(json_path, output_dir, db_dir=None, run_data_pipeline=True,
                   num_seeds=1, num_samples=1, verbose=False):
    """Run AlphaFold3 with given parameters."""
    config = get_config()
    alphafold_script = find_alphafold3(config)

    if not alphafold_script:
        print("ERROR: AlphaFold3 not found. Install from: https://github.com/google-deepmind/alphafold3",
              file=sys.stderr)
        return 2

    if not Path(json_path).exists():
        print(f"ERROR: Input JSON not found: {json_path}", file=sys.stderr)
        return 1

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
    if alphafold_script.startswith("conda run"):
        cmd = alphafold_script.split()
    else:
        cmd = ["python", alphafold_script]

    cmd.extend([
        "--json_path", json_path,
        "--output_dir", output_dir,
    ])

    if db_dir and run_data_pipeline:
        cmd.extend(["--db_dir", db_dir])
    else:
        cmd.append("--run_data_pipeline=false")

    if num_seeds > 1:
        cmd.extend(["--num_seeds", str(num_seeds)])

    if num_samples > 1:
        cmd.extend(["--num_samples", str(num_samples)])

    if verbose:
        print(f"Running: {' '.join(cmd)}")
        if db_dir:
            print(f"Using databases: {db_dir}")
        else:
            print("Running without MSA (no databases)")

    start_time = time.time()
    try:
        result = subprocess.run(
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


def main():
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
  python run_alphafold3.py --json design.json --output-dir outputs/af3/ --num-seeds 5 --num-samples 5

  # With custom database path
  python run_alphafold3.py --json design.json --output-dir outputs/af3/ --db-dir /path/to/databases
        """
    )
    parser.add_argument("--json", "-j", required=True,
                        help="AlphaFold3 JSON input file")
    parser.add_argument("--output-dir", "-o", required=True,
                        help="Output directory")
    parser.add_argument("--db-dir", "-d",
                        help="Path to AlphaFold3 databases (~2.6TB)")
    parser.add_argument("--no-msa", action="store_true",
                        help="Skip MSA search (faster, less accurate)")
    parser.add_argument("--num-seeds", type=int, default=1,
                        help="Number of random seeds (default: 1)")
    parser.add_argument("--num-samples", type=int, default=1,
                        help="Samples per seed (default: 1)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return run_alphafold3(
        json_path=args.json,
        output_dir=args.output_dir,
        db_dir=args.db_dir,
        run_data_pipeline=not args.no_msa,
        num_seeds=args.num_seeds,
        num_samples=args.num_samples,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
