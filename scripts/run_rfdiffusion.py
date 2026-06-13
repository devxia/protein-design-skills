#!/usr/bin/env python3
"""
Standalone RFdiffusion runner.

Usage: python scripts/run_rfdiffusion.py --config config.yaml [options]

Exit codes:
    0 = Success
    1 = Config file not found
    2 = RFdiffusion not installed / not found
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
                    ["conda", "run", "-n", env, "find", "~", "-name", "run_inference.py", "-path", "*/RFdiffusion/*"],
                    capture_output=True, text=True, timeout=10
                )
                if result2.returncode == 0 and result2.stdout.strip():
                    return result2.stdout.strip().split("\n")[0]
                return f"conda run -n {env} python -m rfdiffusion"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return None


def run_rfdiffusion(config_file=None, output_prefix=None, num_designs=50,
                    contig=None, hotspot_res=None, diffuser_t=50,
                    input_pdb=None, verbose=False):
    """Run RFdiffusion with given parameters."""
    config = get_config("rfdiffusion")
    rfdiffusion_script = find_rfdiffusion(config)

    if not rfdiffusion_script:
        print("ERROR: RFdiffusion not found. Install from: https://github.com/RosettaCommons/RFdiffusion",
              file=sys.stderr)
        return 2

    # Build command
    if rfdiffusion_script.startswith("conda run"):
        cmd = rfdiffusion_script.split()
    else:
        cmd = ["python", rfdiffusion_script]

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

    if input_pdb:
        overrides.append(f"inference.input_pdb={input_pdb}")

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
    parser.add_argument("--config", "-c", help="Hydra config file")
    parser.add_argument("--output-prefix", "-o", help="Output file prefix")
    parser.add_argument("--num-designs", "-n", type=int, default=50, help="Number of designs")
    parser.add_argument("--contig", help="Contig string for generation")
    parser.add_argument("--hotspot-res", help="Hotspot residues (comma-separated)")
    parser.add_argument("--diffuser-t", type=int, default=50, help="Diffusion steps")
    parser.add_argument("--input-pdb", "-i", help="Input PDB for conditional design")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    hotspot_res = args.hotspot_res.split(",") if args.hotspot_res else None

    return run_rfdiffusion(
        config_file=args.config,
        output_prefix=args.output_prefix,
        num_designs=args.num_designs,
        contig=args.contig,
        hotspot_res=hotspot_res,
        diffuser_t=args.diffuser_t,
        input_pdb=args.input_pdb,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
