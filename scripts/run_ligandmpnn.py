#!/usr/bin/env python3
"""
Standalone LigandMPNN runner.

Usage: python scripts/run_ligandmpnn.py --pdb_path structure.pdb --out_folder outputs/ligandmpnn/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = LigandMPNN not installed / not found
    3 = Execution error
    4 = Invalid arguments

Upstream references:
    - https://github.com/dauparas/LigandMPNN
    - Paper: https://www.biorxiv.org/content/10.1101/2024.10.22.619563
    - CLI entry point: python run.py --pdb_path <pdb> --out_folder <dir> [flags]
    - Common flags: --num_seq_per_target, --sampling_temp, --model_type,
      --chains_to_design, --fixed_residues, --redesigned_residues,
      --pack_side_chains, --seed
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history

import argparse
import subprocess
import time


def find_ligandmpnn(config):
    """Locate LigandMPNN installation."""
    # 1. Configured path / environment variable
    if config.get("ligandmpnn_path"):
        path = Path(config["ligandmpnn_path"])
        if path.exists():
            return str(path)

    # 2. Common install locations
    common_paths = [
        Path.home() / "LigandMPNN" / "run.py",
        Path.home() / "ligandmpnn" / "run.py",
        Path("/opt/LigandMPNN/run.py"),
        Path("/usr/local/LigandMPNN/run.py"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    # 3. Conda environments
    conda_envs = ["ligandmpnn", "ligandmpnn_env", "protein-design"]
    for env in conda_envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env, "find", str(Path.home()), "-name", "run.py",
                 "-path", "*/LigandMPNN/*"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                script = result.stdout.strip().split("\n")[0]
                return f"conda run -n {env} python {script}"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        try:
            # Also check whether the package is importable in the env
            result = subprocess.run(
                ["conda", "run", "-n", env, "python", "-c",
                 "import ligandmpnn; print(ligandmpnn.__file__)"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return f"conda run -n {env} python -m ligandmpnn"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # 4. Try which
    try:
        result = subprocess.run(
            ["which", "run.py"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Be cautious: run.py is a generic name, verify it is LigandMPNN
            run_path = Path(result.stdout.strip())
            if (run_path.parent / "get_model_params.sh").exists():
                return str(run_path)
    except FileNotFoundError:
        pass

    return None


def run_ligandmpnn(pdb_path, out_folder, num_seq_per_target=8,
                   sampling_temp="0.1", model_type=None,
                   chains_to_design=None, fixed_residues=None,
                   redesigned_residues=None, seed=None,
                   pack_side_chains=False, number_of_packs_per_design=None,
                   verbose=False):
    """Run LigandMPNN with given parameters."""
    config = get_config("ligandmpnn")
    ligandmpnn_script = find_ligandmpnn(config)

    if not ligandmpnn_script:
        print(
            "ERROR: LigandMPNN not found. Install from: "
            "https://github.com/dauparas/LigandMPNN",
            file=sys.stderr,
        )
        return 2

    if not Path(pdb_path).exists():
        print(f"ERROR: Input file not found: {pdb_path}", file=sys.stderr)
        return 1

    out_path = Path(out_folder)
    out_path.mkdir(parents=True, exist_ok=True)

    # Build command
    if ligandmpnn_script.startswith("conda run"):
        cmd = ligandmpnn_script.split()
    else:
        cmd = ["python", ligandmpnn_script]

    cmd.extend([
        "--pdb_path", pdb_path,
        "--out_folder", out_folder,
        "--num_seq_per_target", str(num_seq_per_target),
        "--sampling_temp", str(sampling_temp),
    ])

    if model_type is not None:
        cmd.extend(["--model_type", model_type])
    if chains_to_design is not None:
        cmd.extend(["--chains_to_design", chains_to_design])
    if fixed_residues is not None:
        cmd.extend(["--fixed_residues", fixed_residues])
    if redesigned_residues is not None:
        cmd.extend(["--redesigned_residues", redesigned_residues])
    if seed is not None:
        cmd.extend(["--seed", str(seed)])
    if pack_side_chains:
        cmd.extend(["--pack_side_chains", "1"])
        if number_of_packs_per_design is not None:
            cmd.extend(["--number_of_packs_per_design", str(number_of_packs_per_design)])

    if verbose:
        print(f"Running: {' '.join(cmd)}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes max
        )
        runtime = time.time() - start_time

        if verbose and result.stdout:
            print(result.stdout[-2000:])

        if result.returncode != 0:
            print(f"ERROR: LigandMPNN failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history(
                "ligandmpnn",
                {"pdb_path": pdb_path, "out_folder": out_folder},
                runtime,
                False,
                config["output_dir"],
            )
            return 3

        # Check output
        fasta_files = list(out_path.glob("**/*.fa")) + list(out_path.glob("**/*.fasta"))
        if not fasta_files:
            print("WARNING: No FASTA output files found", file=sys.stderr)

        log_history(
            "ligandmpnn",
            {"pdb_path": pdb_path, "out_folder": out_folder},
            runtime,
            True,
            config["output_dir"],
        )

        if verbose:
            print(f"SUCCESS: LigandMPNN completed in {runtime:.1f}s")
            print(f"Output: {out_folder}")
            print(f"FASTA files: {len(fasta_files)}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: LigandMPNN timed out (>30 minutes)", file=sys.stderr)
        log_history(
            "ligandmpnn",
            {"pdb_path": pdb_path, "out_folder": out_folder},
            1800,
            False,
            config["output_dir"],
        )
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history(
            "ligandmpnn",
            {"pdb_path": pdb_path, "out_folder": out_folder},
            time.time() - start_time,
            False,
            config["output_dir"],
        )
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run LigandMPNN — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard protein design
  python run_ligandmpnn.py --pdb_path backbone.pdb --out_folder outputs/ligandmpnn/ \
      --num_seq_per_target 8 --sampling_temp "0.1"

  # Ligand-aware design
  python run_ligandmpnn.py --pdb_path protein_with_ligand.pdb \
      --out_folder outputs/ligand_design/ --model_type ligand_mpnn \
      --num_seq_per_target 8 --sampling_temp "0.1" --chains_to_design A

  # Nanobody design
  python run_ligandmpnn.py --pdb_path nanobody.pdb --out_folder outputs/vhh/ \
      --chains_to_design H --num_seq_per_target 16
        """
    )
    parser.add_argument("--pdb_path", "-p", required=True,
                        help="Input PDB file")
    parser.add_argument("--out_folder", "-o", required=True,
                        help="Output folder")
    parser.add_argument("--num_seq_per_target", "--num-seq", "--num-seq-per-target", "-n", type=int, default=8,
                        help="Sequences per target (default: 8)")
    parser.add_argument("--sampling_temp", "--sampling-temp", "--temp", "-t", default="0.1",
                        help="Sampling temperature (default: '0.1')")
    parser.add_argument("--model_type",
                        help="Model variant: protein_mpnn, ligand_mpnn, soluble_mpnn, ...")
    parser.add_argument("--chains_to_design", "--chains", "-c",
                        help="Chains to redesign, e.g. A,B")
    parser.add_argument("--fixed_residues",
                        help="Residues to keep fixed, e.g. 'C1 C2 C3'")
    parser.add_argument("--redesigned_residues",
                        help="Residues to redesign, e.g. 'A1 A2 A3'")
    parser.add_argument("--seed", type=int,
                        help="Random seed")
    parser.add_argument("--pack_side_chains", action="store_true",
                        help="Also pack side chains")
    parser.add_argument("--number_of_packs_per_design", type=int,
                        help="Number of side-chain packs per design")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return run_ligandmpnn(
        pdb_path=args.pdb_path,
        out_folder=args.out_folder,
        num_seq_per_target=args.num_seq_per_target,
        sampling_temp=args.sampling_temp,
        model_type=args.model_type,
        chains_to_design=args.chains_to_design,
        fixed_residues=args.fixed_residues,
        redesigned_residues=args.redesigned_residues,
        seed=args.seed,
        pack_side_chains=args.pack_side_chains,
        number_of_packs_per_design=args.number_of_packs_per_design,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
