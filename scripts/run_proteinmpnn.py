#!/usr/bin/env python3
"""
Standalone ProteinMPNN runner.

Usage: python scripts/run_proteinmpnn.py --pdb-path design.pdb --out-folder outputs/seqs/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = ProteinMPNN not installed / not found
    3 = Execution error
    4 = Invalid arguments
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history

import argparse
import glob
import subprocess
import time


def find_proteinmpnn(config):
    """Locate ProteinMPNN installation."""
    # 1. Configured path
    if config.get("proteinmpnn_path"):
        path = Path(config["proteinmpnn_path"])
        if path.exists():
            return str(path)

    # 2. Common locations
    common_paths = [
        Path.home() / "ProteinMPNN" / "protein_mpnn_run.py",
        Path.home() / "proteinmpnn" / "protein_mpnn_run.py",
        Path.home() / "ProteinMPNN" / "run.py",
        Path("/opt/ProteinMPNN/protein_mpnn_run.py"),
        Path("/usr/local/ProteinMPNN/protein_mpnn_run.py"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    # 3. Conda environments
    conda_envs = ["proteinmpnn", "protein-design"]
    for env in conda_envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env, "python", "-c",
                 "import proteinmpnn; print(proteinmpnn.__file__)"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return f"conda run -n {env} python -m proteinmpnn"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # 4. Try which
    try:
        result = subprocess.run(["which", "protein_mpnn_run.py"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass

    return None


def run_proteinmpnn(pdb_path, out_folder, num_seq_per_target=8,
                    sampling_temp="0.1", pdb_path_chains=None,
                    fixed_positions=None, verbose=False):
    """Run ProteinMPNN with given parameters."""
    config = get_config("proteinmpnn")
    proteinmpnn_script = find_proteinmpnn(config)

    if not proteinmpnn_script:
        print("ERROR: ProteinMPNN not found. Install from: https://github.com/dauparas/ProteinMPNN",
              file=sys.stderr)
        return 2

    # Resolve glob patterns in pdb_path
    pdb_files = glob.glob(pdb_path)
    if not pdb_files:
        print(f"ERROR: No PDB files found matching: {pdb_path}", file=sys.stderr)
        return 1

    # Create output folder
    out_path = Path(out_folder)
    out_path.mkdir(parents=True, exist_ok=True)

    # Build command
    if proteinmpnn_script.startswith("conda run"):
        cmd = proteinmpnn_script.split()
    else:
        cmd = ["python", proteinmpnn_script]

    cmd.extend([
        "--pdb_path", pdb_path,
        "--out_folder", out_folder,
        "--num_seq_per_target", str(num_seq_per_target),
        "--sampling_temp", str(sampling_temp),
    ])

    if pdb_path_chains:
        cmd.extend(["--pdb_path_chains", pdb_path_chains])

    if fixed_positions:
        cmd.extend(["--fixed_positions", fixed_positions])

    if verbose:
        print(f"Running: {' '.join(cmd)}")
        print(f"Input PDBs: {len(pdb_files)} file(s)")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes max
        )
        runtime = time.time() - start_time

        if verbose and result.stdout:
            print(result.stdout[-2000:])

        if result.returncode != 0:
            print(f"ERROR: ProteinMPNN failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history("proteinmpnn",
                        {"pdb_path": pdb_path, "num_seq": num_seq_per_target}, runtime, False,
                        config["output_dir"])
            return 3

        # Check output
        fasta_files = list(out_path.glob("*.fa")) + list(out_path.glob("*.fasta"))
        if not fasta_files:
            print("WARNING: No FASTA output files found", file=sys.stderr)

        log_history("proteinmpnn",
                    {"pdb_path": pdb_path, "num_seq": num_seq_per_target}, runtime, True,
                    config["output_dir"])

        if verbose:
            print(f"SUCCESS: ProteinMPNN completed in {runtime:.1f}s")
            print(f"Output: {out_folder}")
            print(f"FASTA files: {len(fasta_files)}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: ProteinMPNN timed out (>30 minutes)", file=sys.stderr)
        log_history("proteinmpnn", {"pdb_path": pdb_path}, 1800, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("proteinmpnn", {"pdb_path": pdb_path}, time.time() - start_time, False,
                    config["output_dir"])
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run ProteinMPNN — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic sequence design
  python run_proteinmpnn.py --pdb-path design.pdb --out-folder outputs/seqs/

  # Multiple designs with higher diversity
  python run_proteinmpnn.py --pdb-path "designs/*.pdb" --out-folder outputs/seqs/ --num-seq 8 --temp "0.1 0.2"

  # Design only specific chain
  python run_proteinmpnn.py --pdb-path design.pdb --out-folder outputs/seqs/ --chains B
        """
    )
    parser.add_argument("--pdb-path", "-p", required=True,
                        help="Input PDB file or glob pattern")
    parser.add_argument("--out-folder", "-o", required=True,
                        help="Output folder for sequences")
    parser.add_argument("--num-seq", "--num-seq-per-target", "-n", type=int, default=8,
                        help="Sequences per target (default: 8)")
    parser.add_argument("--temp", "--sampling-temp", "-t", default="0.1",
                        help="Sampling temperature (default: 0.1)")
    parser.add_argument("--chains", "--pdb-path-chains", "-c",
                        help="Chain IDs to design (comma-separated)")
    parser.add_argument("--fixed-positions",
                        help="Fixed positions (comma-separated indices)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return run_proteinmpnn(
        pdb_path=args.pdb_path,
        out_folder=args.out_folder,
        num_seq_per_target=args.num_seq,
        sampling_temp=args.temp,
        pdb_path_chains=args.chains,
        fixed_positions=args.fixed_positions,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
