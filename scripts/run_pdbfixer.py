#!/usr/bin/env python3
"""
Standalone PDBFixer runner.

Usage: python scripts/run_pdbfixer.py --input input.pdb --output fixed.pdb [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = PDBFixer not installed / not found
    3 = Processing error
    4 = Invalid arguments
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history
from protein_design.conda_utils import find_conda_env, build_tool_command, resolve_wrapper_script, is_bare_executable

import argparse
import subprocess
import time


def find_pdbfixer(config):
    """Locate PDBFixer executable or Python module."""
    # 1. Configured path
    if config.get("pdbfixer_path"):
        path = Path(config["pdbfixer_path"])
        if path.exists():
            return str(path)

    # 2. Common conda environment names
    env = find_conda_env(
        ["pdbfixer", "openmm", "protein-design"],
        "import pdbfixer; print(pdbfixer.__file__)",
    )
    if env is not None:
        return f"conda run -n {env} python -m pdbfixer"

    # 3. Try direct python -m pdbfixer
    try:
        result = subprocess.run(
            ["python", "-c", "import pdbfixer; print('ok')"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "python -m pdbfixer"
    except FileNotFoundError:
        pass

    # 4. Try PATH
    for cmd in ["pdbfixer", "PDBFixer"]:
        try:
            result = subprocess.run(["which", cmd], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return cmd
        except FileNotFoundError:
            continue

    return None


def run_pdbfixer(input_pdb, output_pdb, keep_chains=None, add_atoms="heavy",
                 keep_heterogens=None, ph=7.0, verbose=False):
    """Run PDBFixer on input PDB and write to output."""
    config = get_config("pdbfixer")
    pdbfixer_cmd = find_pdbfixer(config)

    if not pdbfixer_cmd:
        print("ERROR: PDBFixer not found. Install with: conda install -c conda-forge pdbfixer", file=sys.stderr)
        return 2

    if not Path(input_pdb).exists():
        print(f"ERROR: Input file not found: {input_pdb}", file=sys.stderr)
        return 1

    # Build PDBFixer command
    wrapper = resolve_wrapper_script(config, "pdbfixer")
    cmd = build_tool_command(
        pdbfixer_cmd, wrapper_script=wrapper, bare_executable=is_bare_executable(pdbfixer_cmd)
    )
    cmd.append(input_pdb)

    # Add options
    cmd.extend(["--output", output_pdb])

    if keep_chains:
        cmd.extend(["--keep-chains", keep_chains])

    if add_atoms:
        cmd.extend(["--add-atoms", add_atoms])

    if keep_heterogens:
        cmd.extend(["--keep-heterogens", keep_heterogens])

    if add_atoms != "none":
        cmd.extend(["--ph", str(ph)])

    if verbose:
        print(f"Running: {' '.join(cmd)}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes max
        )
        runtime = time.time() - start_time

        if verbose and result.stdout:
            print(result.stdout)

        if result.returncode != 0:
            print(f"ERROR: PDBFixer failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            log_history("pdbfixer", {"input": input_pdb}, runtime, False, config["output_dir"])
            return 3

        if not Path(output_pdb).exists():
            print(f"ERROR: Output file not created: {output_pdb}", file=sys.stderr)
            log_history("pdbfixer", {"input": input_pdb}, runtime, False, config["output_dir"])
            return 3

        log_history("pdbfixer", {"input": input_pdb}, runtime, True, config["output_dir"])

        if verbose:
            print(f"SUCCESS: Fixed PDB written to {output_pdb}")
            print(f"Runtime: {runtime:.1f}s")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: PDBFixer timed out (>10 minutes)", file=sys.stderr)
        log_history("pdbfixer", {"input": input_pdb}, 600, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("pdbfixer", {"input": input_pdb}, time.time() - start_time, False, config["output_dir"])
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run PDBFixer — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pdbfixer.py --input structure.pdb --output fixed.pdb
  python run_pdbfixer.py --input structure.pdb --output fixed.pdb --keep-chains A,B
  python run_pdbfixer.py --input structure.pdb --output fixed.pdb --add-atoms all --verbose
        """
    )
    parser.add_argument("--input", "-i", required=True, help="Input PDB file")
    parser.add_argument("--output", "-o", required=True, help="Output fixed PDB file")
    parser.add_argument("--keep-chains", help="Comma-separated chain IDs to keep (e.g., A,B)")
    parser.add_argument("--add-atoms", default="heavy", choices=["heavy", "all", "none"],
                        help="Which atoms to add (default: heavy)")
    parser.add_argument("--keep-heterogens", help="Heterogens to keep (e.g., water, all)")
    parser.add_argument("--ph", type=float, default=7.0, help="pH for hydrogen addition (default: 7.0)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    return run_pdbfixer(
        input_pdb=args.input,
        output_pdb=args.output,
        keep_chains=args.keep_chains,
        add_atoms=args.add_atoms,
        keep_heterogens=args.keep_heterogens,
        ph=args.ph,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
