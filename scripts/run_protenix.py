#!/usr/bin/env python3
"""
Standalone Protenix runner.

Usage: python scripts/run_protenix.py --input input.json --output-dir outputs/protenix/ [options]

Invokes Protenix as ``protenix predict --input <json> --out_dir <dir> --cycle N``
(Protenix v0.5.x form). When the installed CLI only accepts the newer ``pred``
subcommand (``protenix pred -i <json> -o <dir>``), that form is used instead.
The script's ``--num-recycling`` flag maps to Protenix's ``--cycle`` flag.

Exit codes:
    0 = Success
    1 = Input file not found
    2 = Protenix not installed / not found (argparse usage errors also exit 2)
    3 = Execution error
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history
from protein_design.conda_utils import probe_conda_envs, build_tool_command, resolve_wrapper_script, is_bare_executable, resolve_configured_path
from protein_design.process_utils import run_process

import argparse
import json
import shlex
import shutil
import subprocess
import time


def find_protenix():
    """Locate Protenix installation."""
    config = get_config("protenix")
    # 0. Configured path / environment variable.  Resolve the known console
    # entry point when a project or bin directory is configured.
    configured = resolve_configured_path(
        config.get("protenix_path"), ["protenix", "bin/protenix"]
    )
    if configured:
        return configured

    # 1. Try direct command on PATH.
    if shutil.which("protenix"):
        return "protenix"

    # 2. Conda environments
    env = probe_conda_envs(["protenix", "protein-design"], ["protenix", "--help"])
    if env is not None:
        return f"conda run -n {env} protenix"

    # 3. pip-installed in current env
    try:
        result = subprocess.run(
            [sys.executable, "-m", "protenix", "--help"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return shlex.join([sys.executable, "-m", "protenix"])
    except (subprocess.TimeoutExpired, OSError):
        pass

    return None


def _probe_subcommand(base_argv, subcommand):
    """Return True if ``<base_argv> <subcommand> --help`` exits 0."""
    try:
        result = subprocess.run(
            base_argv + [subcommand, "--help"],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _resolve_predict_form(base_argv, verbose=False):
    """Decide how to invoke prediction on the installed Protenix CLI.

    Protenix v0.5.x uses ``predict --input <json> --out_dir <dir>``; newer
    releases renamed the subcommand to ``pred`` with short flags
    (``pred -i <json> -o <dir>``). Probe ``--help`` to detect which form the
    installed version accepts. When neither probe succeeds, fall back to the
    v0.5.x form so the failure surfaces as a normal execution error (exit 3).

    Returns a ``(subcommand, input_flag, out_dir_flag)`` tuple.
    """
    if _probe_subcommand(base_argv, "predict"):
        return ("predict", "--input", "--out_dir")
    if _probe_subcommand(base_argv, "pred"):
        if verbose:
            print("Detected newer Protenix CLI: using 'pred' subcommand")
        return ("pred", "-i", "-o")
    return ("predict", "--input", "--out_dir")


def run_protenix(input_file, out_dir, num_recycling=3, verbose=False, from_fasta=False):
    """Run Protenix prediction."""
    config = get_config("protenix")
    protenix_cmd = find_protenix()

    if not protenix_cmd:
        print("ERROR: Protenix not found. Install with: pip install protenix", file=sys.stderr)
        return 2

    if not Path(input_file).exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Convert FASTA to Protenix JSON only after the tool is confirmed present,
    # so a missing installation leaves no partial output behind.
    if from_fasta:
        from protein_design.utils import read_fasta, fasta_to_alphafold3_json

        json_file = out_path / "protenix_input.json"
        sequences = read_fasta(input_file)
        af3_input = fasta_to_alphafold3_json(
            sequences, job_name="protenix_run"
        )
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(af3_input, f, indent=2)
        input_file = str(json_file)
        if verbose:
            print(f"Converted FASTA to JSON: {input_file}")

    # Build command
    wrapper = resolve_wrapper_script(config, "protenix")
    cmd = build_tool_command(
        protenix_cmd, wrapper_script=wrapper, bare_executable=is_bare_executable(protenix_cmd)
    )
    subcommand, input_flag, out_dir_flag = _resolve_predict_form(cmd, verbose=verbose)
    cmd.extend([subcommand, input_flag, str(input_file), out_dir_flag, str(out_dir)])

    # --num-recycling maps to Protenix's --cycle flag
    if num_recycling != 3:
        cmd.extend(["--cycle", str(num_recycling)])

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
            print(f"ERROR: Protenix failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history("protenix", {"input": input_file}, runtime, False, config["output_dir"])
            return 3

        log_history("protenix", {"input": input_file}, runtime, True, config["output_dir"])

        if verbose:
            print(f"SUCCESS: Protenix completed in {runtime:.1f}s")
            print(f"Output: {out_dir}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: Protenix timed out (>2 hours)", file=sys.stderr)
        log_history("protenix", {"input": input_file}, 7200, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("protenix", {"input": input_file}, time.time() - start_time, False,
                    config["output_dir"])
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run Protenix — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic prediction
  python run_protenix.py --input input.json --output-dir outputs/protenix/

  # With custom recycling steps
  python run_protenix.py --input input.json --output-dir outputs/protenix/ --num-recycling 5

  # From FASTA (auto-convert to Protenix JSON)
  python run_protenix.py --input sequences.fa --output-dir outputs/protenix/ --from-fasta
        """
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input JSON or FASTA file")
    parser.add_argument("--output-dir", "--out-dir", "-o", required=True,
                        help="Output directory")
    parser.add_argument("--num-recycling", type=int, default=3,
                        help="Number of recycling steps, passed to Protenix as --cycle (default: 3)")
    parser.add_argument("--from-fasta", action="store_true",
                        help="Convert FASTA input to Protenix JSON format")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    input_file = args.input

    # Fail fast on a missing input file (exit 1) before tool discovery or any
    # FASTA-conversion side effects.
    if not Path(input_file).exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    return run_protenix(
        input_file=input_file,
        out_dir=args.output_dir,
        num_recycling=args.num_recycling,
        verbose=args.verbose,
        from_fasta=args.from_fasta,
    )


if __name__ == "__main__":
    sys.exit(main())
