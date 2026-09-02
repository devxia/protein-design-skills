#!/usr/bin/env python3
"""
Standalone PDBFixer runner.

Usage: python scripts/run_pdbfixer.py --input input.pdb --output fixed.pdb [options]

PDBFixer is a library, not a CLI. This runner performs the repair through a
small embedded wrapper that calls ``pdbfixer.PDBFixer`` directly, running it
inside a conda environment when one is discovered.

Exit codes:
    0 = Success
    1 = Input file not found
    2 = PDBFixer not installed / not found (argparse usage errors also exit 2)
    3 = Processing error
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history
from protein_design.conda_utils import find_conda_env, resolve_wrapper_script
from protein_design.process_utils import run_process

import argparse
import subprocess
import time


# Embedded script that performs the actual repair via the PDBFixer library.
PDBFIXER_WRAPPER = """\
import sys
from pdbfixer import PDBFixer
from openmm.app import PDBFile

input_pdb = sys.argv[1]
output_pdb = sys.argv[2]
keep_chains = sys.argv[3] if len(sys.argv) > 3 else ""
add_atoms = sys.argv[4] if len(sys.argv) > 4 else "heavy"
keep_heterogens = sys.argv[5] if len(sys.argv) > 5 else ""
ph = float(sys.argv[6]) if len(sys.argv) > 6 else 7.0

fixer = PDBFixer(filename=input_pdb)

if keep_chains:
    wanted = {c.strip() for c in keep_chains.split(",") if c.strip()}
    fixer.removeChains([c.id for c in fixer.topology.chains() if c.id not in wanted])

fixer.findMissingResidues()
fixer.findNonstandardResidues()
fixer.replaceNonstandardResidues()

if not (keep_heterogens and keep_heterogens.lower() == "all"):
    fixer.removeHeterogens(keepWater=bool(keep_heterogens) and "water" in keep_heterogens.lower())

if add_atoms in ("heavy", "all"):
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
if add_atoms == "all":
    fixer.addMissingHydrogens(ph)

with open(output_pdb, "w") as out:
    PDBFile.writeFile(fixer.topology, fixer.positions, out)
"""


def find_pdbfixer_python(config):
    """Return the Python interpreter prefix that can import PDBFixer.

    Returns a list like ``["conda", "run", "-n", env, "python"]`` or
    ``[sys.executable]``, or ``None`` if PDBFixer is not importable anywhere.
    """
    # 1. Conda environment with pdbfixer importable.
    env = find_conda_env(
        ["pdbfixer", "openmm", "protein-design"],
        "import pdbfixer",
    )
    if env is not None:
        return ["conda", "run", "-n", env, "python"]

    # 2. Current interpreter can import pdbfixer.
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import pdbfixer"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return [sys.executable]
    except FileNotFoundError:
        pass

    return None


def run_pdbfixer(input_pdb, output_pdb, keep_chains=None, add_atoms="heavy",
                 keep_heterogens=None, ph=7.0, verbose=False):
    """Run PDBFixer on input PDB and write to output."""
    config = get_config("pdbfixer")
    python_prefix = find_pdbfixer_python(config)

    if not python_prefix:
        print("ERROR: PDBFixer not found. Install with: conda install -c conda-forge pdbfixer openmm", file=sys.stderr)
        return 2

    if not Path(input_pdb).exists():
        print(f"ERROR: Input file not found: {input_pdb}", file=sys.stderr)
        return 1

    cmd = list(python_prefix)
    cmd.extend([
        "-c", PDBFIXER_WRAPPER,
        input_pdb,
        output_pdb,
        keep_chains or "",
        add_atoms or "heavy",
        keep_heterogens or "",
        str(ph),
    ])

    wrapper = resolve_wrapper_script(config, "pdbfixer")
    if wrapper:
        cmd = [wrapper] + cmd

    if verbose:
        print(f"Running: {' '.join(cmd[:5])} ... (embedded PDBFixer wrapper)")

    start_time = time.time()
    try:
        result = run_process(
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
        log_history("pdbfixer", {"input": input_pdb}, time.time() - start_time, False,
                    config["output_dir"])
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
