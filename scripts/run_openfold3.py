#!/usr/bin/env python3
"""
Standalone OpenFold3 runner.

Usage: python scripts/run_openfold3.py --input input.fasta --output-dir outputs/openfold3/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = OpenFold3 not installed / not found (argparse usage errors also exit 2)
    3 = Execution error

Note: OpenFold3 is an open-source reimplementation of AlphaFold3.
It may require manual model weight downloads and database setup.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history
from protein_design.conda_utils import build_tool_command, resolve_wrapper_script, resolve_configured_path
from protein_design.process_utils import run_process

import argparse
import shutil
import subprocess
import time


def find_openfold3(config):
    """Locate OpenFold3 installation."""
    # 1. Configured path / environment variable.  Resolve only OpenFold3's
    # known script/console entry points when a directory is configured.
    configured = resolve_configured_path(
        config.get("openfold3_path"),
        [
            "run_pretrained_openfold.py",
            "scripts/run_pretrained_openfold.py",
            "openfold3",
            "openfold-run",
            "bin/openfold3",
            "bin/openfold-run",
        ],
    )
    if configured:
        return configured

    # 2. Try direct CLI entry points on PATH.
    if shutil.which("openfold3"):
        return "openfold3"
    if shutil.which("openfold-run"):
        return "openfold-run"

    # 4. Conda environments
    conda_envs = ["openfold3", "openfold", "protein-design"]
    for env in conda_envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env, "python", "-c", "import openfold; print('ok')"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return f"conda_api:{env}"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # 5. Check common install paths
    common_paths = [
        Path.home() / "software" / "openfold3",
        Path.home() / "software" / "openfold",
        Path("/opt") / "openfold3",
    ]
    for path in common_paths:
        if (path / "run_pretrained_openfold.py").exists():
            return str(path / "run_pretrained_openfold.py")
        if (path / "scripts" / "run_pretrained_openfold.py").exists():
            return str(path / "scripts" / "run_pretrained_openfold.py")

    return None


def run_openfold3(input_file, out_dir, model_dir=None, db_dir=None,
                  num_recycling=3, verbose=False):
    """Run OpenFold3 prediction."""
    config = get_config("openfold3")
    # CLI --db-dir wins; fall back to OPENFOLD3_DB_DIR / ALPHAFOLD*_DB_DIR
    if not db_dir:
        db_dir = config.get("db_dir")
    openfold_cmd = find_openfold3(config)

    if not openfold_cmd:
        print("ERROR: OpenFold3 not found.", file=sys.stderr)
        print("Install: pip install openfold or clone https://github.com/aqlaboratory/openfold3",
              file=sys.stderr)
        return 2

    if not Path(input_file).exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Build command based on installation type (wrapper applies to all forms)
    wrapper = resolve_wrapper_script(config, "openfold3")
    if openfold_cmd.startswith("conda_api:"):
        cmd = build_tool_command(openfold_cmd, wrapper_script=wrapper)
        if Path(input_file).suffix == ".json":
            cmd.extend(["-m", "openfold", "infer", str(input_file)])
        else:
            cmd.extend(["-m", "openfold", "infer", "--fasta", str(input_file)])
        cmd.extend(["--output_dir", str(out_dir)])

    elif openfold_cmd.endswith("run_pretrained_openfold.py"):
        cmd = build_tool_command(openfold_cmd, wrapper_script=wrapper)
        cmd.extend(["--fasta_paths", str(input_file)])
        cmd.extend(["--output_dir", str(out_dir)])
        if model_dir:
            cmd.extend(["--model_dir", model_dir])
        if db_dir:
            cmd.extend(["--data_dir", db_dir])

    else:
        # Direct CLI
        cmd = build_tool_command(openfold_cmd, wrapper_script=wrapper)
        if Path(input_file).suffix == ".json":
            cmd.extend(["infer", str(input_file)])
        else:
            cmd.extend(["infer", "--fasta", str(input_file)])
        cmd.extend(["--output_dir", str(out_dir)])

    if num_recycling != 3:
        cmd.extend(["--num_recycling", str(num_recycling)])

    if verbose:
        print(f"Running: {' '.join(cmd)}")

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
            print(f"ERROR: OpenFold3 failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history("openfold3", {"input": input_file}, runtime, False, config["output_dir"])
            return 3

        log_history("openfold3", {"input": input_file}, runtime, True, config["output_dir"])

        if verbose:
            print(f"SUCCESS: OpenFold3 completed in {runtime:.1f}s")
            print(f"Output: {out_dir}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: OpenFold3 timed out (>2 hours)", file=sys.stderr)
        log_history("openfold3", {"input": input_file}, 7200, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("openfold3", {"input": input_file}, time.time() - start_time, False,
                    config["output_dir"])
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run OpenFold3 — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic prediction from FASTA
  python run_openfold3.py --input sequences.fasta --output-dir outputs/openfold3/

  # With custom model directory
  python run_openfold3.py --input sequences.fasta --output-dir outputs/openfold3/ \
      --model-dir /path/to/model/weights

  # With custom database directory
  python run_openfold3.py --input sequences.fasta --output-dir outputs/openfold3/ \
      --db-dir /path/to/databases

  # From AlphaFold3-style JSON
  python run_openfold3.py --input input.json --output-dir outputs/openfold3/

Note: OpenFold3 requires model weights and genetic databases to be
manually downloaded and configured. See the OpenFold3 repository for
detailed setup instructions.
        """
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input FASTA or JSON file")
    parser.add_argument("--output-dir", "--out-dir", "-o", required=True,
                        help="Output directory")
    parser.add_argument("--model-dir",
                        help="Path to OpenFold3 model weights directory")
    parser.add_argument("--db-dir",
                        help="Path to genetic databases directory")
    parser.add_argument("--num-recycling", type=int, default=3,
                        help="Number of recycling steps (default: 3)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return run_openfold3(
        input_file=args.input,
        out_dir=args.output_dir,
        model_dir=args.model_dir,
        db_dir=args.db_dir,
        num_recycling=args.num_recycling,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
