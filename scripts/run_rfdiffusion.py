#!/usr/bin/env python3
"""
Standalone RFdiffusion runner.

Usage: python scripts/run_rfdiffusion.py [options]

All user-supplied input structures are automatically preprocessed with
PDBFixer before being passed to RFdiffusion. Use ``--skip-preprocessing`` to
opt out (e.g. when the input has already been repaired).

Exit codes:
    0 = Success
    1 = Config file not found
    2 = RFdiffusion not installed / not found
    3 = Execution error
    4 = Invalid arguments
    5 = PDBFixer preprocessing failed
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from protein_design.utils import get_config, log_history
from protein_design.conda_utils import build_tool_command, resolve_wrapper_script

import argparse
import subprocess
import time


def preprocess_for_design(input_pdb, output_dir=None, verbose=False):
    """Run PDBFixer on ``input_pdb`` and return the repaired PDB path.

    This enforces the plugin's mandatory-preprocessing rule: every
    user-supplied structure is repaired (missing atoms, heavy-atom addition,
    heterogen handling) before entering the design pipeline.

    Args:
        input_pdb: Path to the user-supplied input PDB.
        output_dir: Directory for the repaired file. Defaults to the sibling
            ``<input>.fixed.pdb`` next to the input.
        verbose: Forwarded to ``run_pdbfixer`` for progress output.

    Returns:
        Path to the repaired PDB file, or ``None`` if preprocessing failed.
    """
    from run_pdbfixer import run_pdbfixer

    input_path = Path(input_pdb)
    if output_dir:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        fixed_path = out_dir / f"{input_path.stem}.fixed.pdb"
    else:
        fixed_path = input_path.with_suffix(".fixed.pdb")

    if verbose:
        print(f"Preprocessing {input_pdb} with PDBFixer -> {fixed_path}")

    exit_code = run_pdbfixer(
        input_pdb=str(input_path),
        output_pdb=str(fixed_path),
        add_atoms="heavy",
        verbose=verbose,
    )

    if exit_code != 0 or not fixed_path.exists():
        print(f"ERROR: PDBFixer preprocessing failed (exit code {exit_code})",
              file=sys.stderr)
        return None

    if verbose:
        print(f"Preprocessing complete: {fixed_path}")

    return str(fixed_path)


def find_rfdiffusion(config):
    """Locate RFdiffusion installation."""
    # 1. Configured path
    if config.get("rfdiffusion_path"):
        path = Path(config["rfdiffusion_path"])
        if path.exists():
            return str(path)

    # 2. Common locations
    common_paths = [
        Path.home() / "RFdiffusion" / "scripts" / "run_inference.py",
        Path.home() / "rfdiffusion" / "scripts" / "run_inference.py",
        Path.home() / "RFdiffusion" / "run_inference.py",
        Path("/opt/RFdiffusion/scripts/run_inference.py"),
        Path("/usr/local/RFdiffusion/scripts/run_inference.py"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    # 3. Conda environments
    conda_envs = ["SE3nv", "rfdiffusion", "protein-design"]
    for env in conda_envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env, "python", "-c",
                 "import rfdiffusion; print(rfdiffusion.__file__)"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                # Try to find run_inference.py
                result2 = subprocess.run(
                    ["conda", "run", "-n", env, "find", str(Path.home()), "-name", "run_inference.py", "-path", "*/RFdiffusion/*"],
                    capture_output=True, text=True, timeout=10
                )
                if result2.returncode == 0 and result2.stdout.strip():
                    return result2.stdout.strip().split("\n")[0]
                return f"conda run -n {env} python -m rfdiffusion"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return None


def run_rfdiffusion(output_prefix=None, num_designs=50,
                    contig=None, hotspot_res=None, diffuser_t=50,
                    input_pdb=None, skip_preprocessing=False, verbose=False):
    """Run RFdiffusion with given parameters.

    When ``input_pdb`` is supplied and ``skip_preprocessing`` is False (the
    default), the input is first repaired with PDBFixer via
    :func:`preprocess_for_design` and the repaired file is passed to
    RFdiffusion. Pass ``skip_preprocessing=True`` only when the input has
    already been preprocessed.
    """
    config = get_config("rfdiffusion")
    rfdiffusion_script = find_rfdiffusion(config)

    if not rfdiffusion_script:
        print("ERROR: RFdiffusion not found. Install from: https://github.com/RosettaCommons/RFdiffusion",
              file=sys.stderr)
        return 2

    # Mandatory preprocessing: repair user-supplied structures before design.
    effective_input_pdb = input_pdb
    if input_pdb and not skip_preprocessing:
        fixed = preprocess_for_design(input_pdb, output_dir=config["output_dir"], verbose=verbose)
        if fixed is None:
            return 5
        effective_input_pdb = fixed

    # Build command
    wrapper = resolve_wrapper_script(config, "rfdiffusion")
    cmd = build_tool_command(rfdiffusion_script, wrapper_script=wrapper)

    # Add Hydra config overrides
    overrides = []

    if output_prefix:
        overrides.append(f"inference.output_prefix={output_prefix}")
    else:
        output_dir = Path(config["output_dir"]) / "rfdiffusion"
        output_dir.mkdir(parents=True, exist_ok=True)
        overrides.append(f"inference.output_prefix={output_dir}/design")

    if num_designs:
        overrides.append(f"inference.num_designs={num_designs}")

    if contig:
        overrides.append(f"contigmap.contigs=[\"{contig}\"]")

    if hotspot_res:
        hotspots = ",".join(hotspot_res) if isinstance(hotspot_res, list) else hotspot_res
        overrides.append(f"ppi.hotspot_res=[\"{hotspots}\"]")

    if diffuser_t:
        overrides.append(f"diffuser.T={diffuser_t}")

    if effective_input_pdb:
        overrides.append(f"inference.input_pdb={effective_input_pdb}")

    cmd.extend(overrides)

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
            print(result.stdout[-2000:])  # Last 2000 chars

        if result.returncode != 0:
            print(f"ERROR: RFdiffusion failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history("rfdiffusion", {"contig": contig, "num_designs": num_designs}, runtime, False,
                        config["output_dir"])
            return 3

        log_history("rfdiffusion", {"contig": contig, "num_designs": num_designs}, runtime, True,
                    config["output_dir"])

        if verbose:
            print(f"SUCCESS: RFdiffusion completed in {runtime:.1f}s")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: RFdiffusion timed out (>1 hour)", file=sys.stderr)
        log_history("rfdiffusion", {"contig": contig}, 3600, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("rfdiffusion", {"contig": contig}, time.time() - start_time, False,
                    config["output_dir"])
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run RFdiffusion — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Unconditional design
  python run_rfdiffusion.py --contig "150-150" --num-designs 50

  # Binder design
  python run_rfdiffusion.py --input-pdb target.pdb --contig "[B1-100/0 100-100]" --hotspot-res A30,A33

  # Motif scaffolding
  python run_rfdiffusion.py --input-pdb motif.pdb --contig "[A1-10/0 50-60/A11-20]" --num-designs 100
        """
    )
    parser.add_argument("--output-prefix", "-o", help="Output file prefix")
    parser.add_argument("--num-designs", "-n", type=int, default=50, help="Number of designs")
    parser.add_argument("--contig", help="Contig string for generation")
    parser.add_argument("--hotspot-res", help="Hotspot residues (comma-separated)")
    parser.add_argument("--diffuser-t", "--diffuser-T", type=int, default=50, help="Diffusion steps")
    parser.add_argument("--input-pdb", "-i", help="Input PDB for conditional design")
    parser.add_argument("--skip-preprocessing", action="store_true",
                        help="Skip automatic PDBFixer preprocessing (use only if input is already repaired)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    hotspot_res = args.hotspot_res.split(",") if args.hotspot_res else None

    return run_rfdiffusion(
        output_prefix=args.output_prefix,
        num_designs=args.num_designs,
        contig=args.contig,
        hotspot_res=hotspot_res,
        diffuser_t=args.diffuser_t,
        input_pdb=args.input_pdb,
        skip_preprocessing=args.skip_preprocessing,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
