#!/usr/bin/env python3
"""
Standalone Boltz-1 runner.

Usage: python scripts/run_boltz.py --input input.yaml --out-dir outputs/boltz/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = Boltz-1 not installed / not found
    3 = Execution error
    4 = Invalid arguments
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history

import argparse
import subprocess
import time


def find_boltz():
    """Locate Boltz-1 installation."""
    # 1. Try direct command
    try:
        result = subprocess.run(
            ["which", "boltz"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return "boltz"
    except FileNotFoundError:
        pass

    # 2. Conda environments
    conda_envs = ["boltz", "boltz-1", "protein-design"]
    for env in conda_envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env, "boltz", "--help"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return f"conda run -n {env} boltz"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # 3. pip-installed in current env
    try:
        result = subprocess.run(
            ["python", "-m", "boltz", "--help"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "python -m boltz"
    except FileNotFoundError:
        pass

    return None


def run_boltz(input_file, out_dir, use_msa_server=True, recycling_steps=3,
              sampling_steps=200, verbose=False):
    """Run Boltz-1 prediction."""
    config = get_config("boltz")
    boltz_cmd = find_boltz()

    if not boltz_cmd:
        print("ERROR: Boltz-1 not found. Install with: pip install boltz", file=sys.stderr)
        return 2

    if not Path(input_file).exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    # Create output directory
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Build command
    if boltz_cmd.startswith("conda run"):
        cmd = boltz_cmd.split() + ["predict", input_file]
    elif boltz_cmd == "python -m boltz":
        cmd = ["python", "-m", "boltz", "predict", input_file]
    else:
        cmd = [boltz_cmd, "predict", input_file]

    cmd.extend(["--out_dir", out_dir])

    if use_msa_server:
        cmd.append("--use_msa_server")

    if recycling_steps != 3:
        cmd.extend(["--recycling_steps", str(recycling_steps)])

    if sampling_steps != 200:
        cmd.extend(["--sampling_steps", str(sampling_steps)])

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
            print(f"ERROR: Boltz-1 failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history("boltz", {"input": input_file}, runtime, False, config["output_dir"])
            return 3

        log_history("boltz", {"input": input_file}, runtime, True, config["output_dir"])

        if verbose:
            print(f"SUCCESS: Boltz-1 completed in {runtime:.1f}s")
            print(f"Output: {out_dir}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: Boltz-1 timed out (>1 hour)", file=sys.stderr)
        log_history("boltz", {"input": input_file}, 3600, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("boltz", {"input": input_file}, time.time() - start_time, False,
                    config["output_dir"])
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run Boltz-1 — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic prediction with MSA server
  python run_boltz.py --input input.yaml --out-dir outputs/boltz/

  # Without MSA (faster, less accurate)
  python run_boltz.py --input input.yaml --out-dir outputs/boltz/ --no-msa

  # With custom parameters
  python run_boltz.py --input input.yaml --out-dir outputs/boltz/ --recycling-steps 5 --sampling-steps 500
        """
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input YAML or FASTA file")
    parser.add_argument("--out-dir", "--output-dir", "-o", required=True,
                        help="Output directory")
    parser.add_argument("--no-msa", action="store_true",
                        help="Skip MSA server (faster, less accurate)")
    parser.add_argument("--recycling-steps", type=int, default=3,
                        help="Number of recycling steps (default: 3)")
    parser.add_argument("--sampling-steps", type=int, default=200,
                        help="Diffusion sampling steps (default: 200)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return run_boltz(
        input_file=args.input,
        out_dir=args.out_dir,
        use_msa_server=not args.no_msa,
        recycling_steps=args.recycling_steps,
        sampling_steps=args.sampling_steps,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
