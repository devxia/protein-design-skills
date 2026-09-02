#!/usr/bin/env python3
"""
Standalone ProteinMPNN runner.

Usage: python scripts/run_proteinmpnn.py --pdb-path design.pdb --out-folder outputs/seqs/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = ProteinMPNN not installed / not found (argparse usage errors also exit 2)
    3 = Execution error
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history
from protein_design.conda_utils import find_conda_env, build_tool_command, resolve_wrapper_script, resolve_configured_path
from protein_design.process_utils import run_process

import argparse
import glob
import shutil
import subprocess
import time


def find_proteinmpnn(config):
    """Locate ProteinMPNN installation."""
    # 1. Configured path.  A directory must contain ProteinMPNN's specific
    # entry point; do not guess a generic run.py here.
    configured = resolve_configured_path(
        config.get("proteinmpnn_path"), ["protein_mpnn_run.py"]
    )
    if configured:
        return configured

    # 2. Common locations
    common_paths = [
        Path.home() / "ProteinMPNN" / "protein_mpnn_run.py",
        Path.home() / "proteinmpnn" / "protein_mpnn_run.py",
        Path("/opt/ProteinMPNN/protein_mpnn_run.py"),
        Path("/usr/local/ProteinMPNN/protein_mpnn_run.py"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    # 3. Conda environments
    env = find_conda_env(["proteinmpnn", "protein-design"], "import proteinmpnn")
    if env is not None:
        return f"conda run -n {env} python -m proteinmpnn"

    # 4. Try the console script on PATH.
    path = shutil.which("protein_mpnn_run.py")
    if path:
        return path

    return None


def _expand_pdb_paths(pattern):
    """Expand a PDB path or glob into sorted, regular-file paths."""
    matches = glob.glob(str(pattern), recursive=True)
    return sorted(dict.fromkeys(match for match in matches if Path(match).is_file()))


def _snapshot_files(root):
    """Capture file metadata below ``root`` before a tool invocation."""
    snapshot = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        snapshot[path] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def _new_fasta_files(root, before):
    """Return FASTA files created or changed by the current invocation."""
    fresh = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".fa", ".fasta"}:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        metadata = (stat.st_mtime_ns, stat.st_size)
        if before.get(path) != metadata:
            fresh.append(path)
    return sorted(fresh)


def run_proteinmpnn(pdb_path, out_folder, num_seq_per_target=8,
                    sampling_temp="0.1", pdb_path_chains=None,
                    fixed_positions=None, verbose=False):
    """Run ProteinMPNN once per input PDB and collect fresh FASTA outputs."""
    config = get_config("proteinmpnn")
    pdb_files = _expand_pdb_paths(pdb_path)
    if not pdb_files:
        print(f"ERROR: No PDB files found matching: {pdb_path}", file=sys.stderr)
        return 1

    proteinmpnn_script = find_proteinmpnn(config)
    if not proteinmpnn_script:
        print("ERROR: ProteinMPNN not found. Install from: https://github.com/dauparas/ProteinMPNN",
              file=sys.stderr)
        return 2

    out_path = Path(out_folder)
    out_path.mkdir(parents=True, exist_ok=True)
    wrapper = resolve_wrapper_script(config, "proteinmpnn")
    base_cmd = build_tool_command(proteinmpnn_script, wrapper_script=wrapper)
    multiple_inputs = len(pdb_files) > 1
    used_target_names = set()
    total_fasta_files = 0

    if verbose:
        print(f"Input PDBs: {len(pdb_files)} file(s)")

    for index, pdb_file in enumerate(pdb_files, 1):
        target_name = Path(pdb_file).stem or f"target_{index}"
        if target_name in used_target_names:
            target_name = f"{target_name}_{index}"
        used_target_names.add(target_name)
        target_out = out_path / "seqs" / target_name if multiple_inputs else out_path
        target_out.mkdir(parents=True, exist_ok=True)
        before = _snapshot_files(target_out)

        cmd = list(base_cmd)
        cmd.extend([
            "--pdb_path", str(pdb_file),
            "--out_folder", str(target_out),
            "--num_seq_per_target", str(num_seq_per_target),
            "--sampling_temp", str(sampling_temp),
        ])
        if pdb_path_chains:
            cmd.extend(["--pdb_path_chains", pdb_path_chains])
        if fixed_positions:
            cmd.extend(["--fixed_positions", fixed_positions])

        if verbose:
            print(f"Running: {' '.join(cmd)}")

        start_time = time.time()
        try:
            result = run_process(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes max
            )
            runtime = time.time() - start_time

            if verbose and result.stdout:
                print(result.stdout[-2000:])

            if result.returncode != 0:
                print(f"ERROR: ProteinMPNN failed for {pdb_file} (exit code {result.returncode})",
                      file=sys.stderr)
                if result.stderr:
                    print(result.stderr[-2000:], file=sys.stderr)
                log_history(
                    "proteinmpnn",
                    {"pdb_path": str(pdb_file), "num_seq": num_seq_per_target},
                    runtime,
                    False,
                    config["output_dir"],
                )
                return 3

            fasta_files = _new_fasta_files(target_out, before)
            if not fasta_files:
                print(f"ERROR: No new FASTA output files found for {pdb_file}", file=sys.stderr)
                log_history(
                    "proteinmpnn",
                    {"pdb_path": str(pdb_file), "num_seq": num_seq_per_target},
                    runtime,
                    False,
                    config["output_dir"],
                )
                return 3

            total_fasta_files += len(fasta_files)
            log_history(
                "proteinmpnn",
                {"pdb_path": str(pdb_file), "num_seq": num_seq_per_target},
                runtime,
                True,
                config["output_dir"],
            )

        except subprocess.TimeoutExpired:
            print(f"ERROR: ProteinMPNN timed out for {pdb_file} (>30 minutes)", file=sys.stderr)
            log_history(
                "proteinmpnn",
                {"pdb_path": str(pdb_file), "num_seq": num_seq_per_target},
                1800,
                False,
                config["output_dir"],
            )
            return 3
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            log_history(
                "proteinmpnn",
                {"pdb_path": str(pdb_file), "num_seq": num_seq_per_target},
                time.time() - start_time,
                False,
                config["output_dir"],
            )
            return 3

    if verbose:
        print(f"SUCCESS: ProteinMPNN completed for {len(pdb_files)} PDB(s)")
        print(f"Output: {out_folder}")
        print(f"FASTA files: {total_fasta_files}")

    return 0


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
