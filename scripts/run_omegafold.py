#!/usr/bin/env python3
"""
Standalone OmegaFold runner.

Usage: python scripts/run_omegafold.py --input sequences.fasta --output-dir outputs/omegafold/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = OmegaFold not installed / not found
    3 = Execution error
    4 = Invalid arguments
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history
from protein_design.conda_utils import probe_conda_envs, build_tool_command, resolve_wrapper_script, is_bare_executable

import argparse
import os
import subprocess
import time


def find_omegafold():
    """Locate OmegaFold installation."""
    # 1. Try direct command
    try:
        result = subprocess.run(
            ["which", "omegafold"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return "omegafold"
    except FileNotFoundError:
        pass

    # 2. Conda environments
    env = probe_conda_envs(["omegafold", "protein-design"], ["omegafold", "--help"])
    if env is not None:
        return f"conda run -n {env} omegafold"

    # 3. pip-installed in current env
    try:
        result = subprocess.run(
            ["python", "-m", "omegafold", "--help"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "python -m omegafold"
    except FileNotFoundError:
        pass

    return None


def run_omegafold(input_file, output_dir, subbatch_size=None, verbose=False):
    """Run OmegaFold prediction."""
    config = get_config("omegafold")
    omegafold_cmd = find_omegafold()

    if not omegafold_cmd:
        print("ERROR: OmegaFold not found. Install with: pip install OmegaFold", file=sys.stderr)
        return 2

    if not Path(input_file).exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    # Create output directory
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Build command
    wrapper = resolve_wrapper_script(config, "omegafold")
    cmd = build_tool_command(
        omegafold_cmd, wrapper_script=wrapper, bare_executable=is_bare_executable(omegafold_cmd)
    )
    cmd.extend([input_file, output_dir])

    if subbatch_size:
        # OmegaFold uses environment variable for subbatch size
        env = os.environ.copy()
        env["SUBBATCH_SIZE"] = str(subbatch_size)
    else:
        env = os.environ

    if verbose:
        print(f"Running: {' '.join(cmd)}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=3600  # 1 hour max
        )
        runtime = time.time() - start_time

        if verbose and result.stdout:
            print(result.stdout[-2000:])

        if result.returncode != 0:
            print(f"ERROR: OmegaFold failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history("omegafold", {"input": input_file}, runtime, False, config["output_dir"])
            return 3

        log_history("omegafold", {"input": input_file}, runtime, True, config["output_dir"])

        if verbose:
            print(f"SUCCESS: OmegaFold completed in {runtime:.1f}s")
            print(f"Output: {output_dir}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: OmegaFold timed out (>1 hour)", file=sys.stderr)
        log_history("omegafold", {"input": input_file}, 3600, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("omegafold", {"input": input_file}, time.time() - start_time, False,
                    config["output_dir"])
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run OmegaFold — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic prediction
  python run_omegafold.py --input sequences.fasta --output-dir outputs/omegafold/

  # With memory control for large sequences
  python run_omegafold.py --input sequences.fasta --output-dir outputs/omegafold/ --subbatch-size 4
        """
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input FASTA file")
    parser.add_argument("--output-dir", "--out-dir", "-o", required=True,
                        help="Output directory")
    parser.add_argument("--subbatch-size", type=int,
                        help="Subbatch size for memory control (lower = less memory)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return run_omegafold(
        input_file=args.input,
        output_dir=args.output_dir,
        subbatch_size=args.subbatch_size,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
