#!/usr/bin/env python3
"""
Standalone Chai-1 runner.

Usage: python scripts/run_chai1.py --input input.fasta --output-dir outputs/chai1/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = Chai-1 not installed / not found
    3 = Execution error
    4 = Invalid arguments
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history

import argparse
import json
import os
import subprocess
import time
from datetime import datetime


def find_chai1():
    """Locate Chai-1 installation."""
    # 1. Try direct command
    try:
        result = subprocess.run(
            ["which", "chai-lab"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return "chai-lab"
    except FileNotFoundError:
        pass

    # 2. Conda environments
    conda_envs = ["chai1", "chai-1", "protein-design"]
    for env in conda_envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env, "chai-lab", "--help"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return f"conda run -n {env} chai-lab"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # 3. pip-installed in current env
    try:
        result = subprocess.run(
            ["python", "-m", "chai_lab", "--help"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "python -m chai_lab"
    except FileNotFoundError:
        pass

    return None


def run_chai1(input_file, output_dir, use_msa_server=True, num_trunk_recycles=3,
              num_diffn_timesteps=200, verbose=False):
    """Run Chai-1 prediction."""
    config = get_config("chai1")
    chai_cmd = find_chai1()

    if not chai_cmd:
        print("ERROR: Chai-1 not found. Install with: pip install chai-lab", file=sys.stderr)
        return 2

    if not Path(input_file).exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    # Create output directory
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Build command
    if chai_cmd.startswith("conda run"):
        cmd = chai_cmd.split() + ["fold", input_file, output_dir]
    elif chai_cmd == "python -m chai_lab":
        cmd = ["python", "-m", "chai_lab", "fold", input_file, output_dir]
    else:
        cmd = [chai_cmd, "fold", input_file, output_dir]

    if use_msa_server:
        cmd.append("--use-msa-server")

    if num_trunk_recycles != 3:
        cmd.extend(["--num-trunk-recycles", str(num_trunk_recycles)])

    if num_diffn_timesteps != 200:
        cmd.extend(["--num-diffn-timesteps", str(num_diffn_timesteps)])

    if verbose:
        print(f"Running: {' '.join(cmd)}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour max
        )
        runtime = time.time() - start_time

        if verbose and result.stdout:
            print(result.stdout[-2000:])

        if result.returncode != 0:
            print(f"ERROR: Chai-1 failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history("chai1", {"input": input_file}, runtime, False, config["output_dir"])
            return 3

        log_history("chai1", {"input": input_file}, runtime, True, config["output_dir"])

        if verbose:
            print(f"SUCCESS: Chai-1 completed in {runtime:.1f}s")
            print(f"Output: {output_dir}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: Chai-1 timed out (>1 hour)", file=sys.stderr)
        log_history("chai1", {"input": input_file}, 3600, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("chai1", {"input": input_file}, time.time() - start_time, False,
                    config["output_dir"])
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run Chai-1 — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic prediction with MSA server
  python run_chai1.py --input input.fasta --output-dir outputs/chai1/

  # Without MSA (faster)
  python run_chai1.py --input input.fasta --output-dir outputs/chai1/ --no-msa

  # With custom parameters
  python run_chai1.py --input input.fasta --output-dir outputs/chai1/ --recycles 5
        """
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input FASTA file")
    parser.add_argument("--output-dir", "-o", required=True,
                        help="Output directory")
    parser.add_argument("--no-msa", action="store_true",
                        help="Skip MSA server")
    parser.add_argument("--recycles", type=int, default=3,
                        help="Number of trunk recycles (default: 3)")
    parser.add_argument("--timesteps", type=int, default=200,
                        help="Diffusion timesteps (default: 200)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return run_chai1(
        input_file=args.input,
        output_dir=args.output_dir,
        use_msa_server=not args.no_msa,
        num_trunk_recycles=args.recycles,
        num_diffn_timesteps=args.timesteps,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
