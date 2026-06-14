#!/usr/bin/env python3
"""
Standalone design filtering and ranking script.
Usage: python scripts/run_filtering.py --results-dir outputs/validation/ [options]

Reads confidence metrics from validation tools (AlphaFold3, Boltz, Chai-1, etc.)
and ranks designs by composite quality score.

Exit codes:
    0 = Success
    1 = Results directory not found
    2 = No valid results found
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import parse_confidence_json

import argparse
import json
from statistics import mean, stdev


def parse_pdb_bfactor(filepath):
    """Extract mean pLDDT from PDB B-factors (ESMFold/OmegaFold output)."""
    try:
        from Bio import PDB
        structure = PDB.PDBParser(QUIET=True).get_structure("x", filepath)
        b_factors = [atom.get_bfactor() for atom in structure.get_atoms()]
        if b_factors:
            return mean(b_factors)
    except ImportError:
        pass
    except Exception:
        pass
    return None


def compute_composite_score(result, weights):
    """Compute weighted composite score from available metrics."""
    score = 0.0
    total_weight = 0.0

    if "plddt" in result and weights.get("plddt"):
        score += result["plddt"] * weights["plddt"]
        total_weight += weights["plddt"]

    if "iptm" in result and weights.get("iptm"):
        score += result["iptm"] * 100 * weights["iptm"]  # Scale to 0-100
        total_weight += weights["iptm"]

    if "ptm" in result and weights.get("ptm"):
        score += result["ptm"] * 100 * weights["ptm"]
        total_weight += weights["ptm"]

    if "pae" in result and weights.get("pae"):
        # Lower PAE is better, so invert
        pae_score = max(0, 100 - result["pae"] * 10)
        score += pae_score * weights["pae"]
        total_weight += weights["pae"]

    if total_weight > 0:
        return score / total_weight
    return 0.0


def filter_designs(results_dir, min_plddt=70, min_iptm=0.6, min_ptm=0.7,
                   max_pae=10.0, top_n=None, weights=None, verbose=False):
    """Filter and rank designs from validation results."""
    results_path = Path(results_dir)
    if not results_path.exists():
        print(f"ERROR: Results directory not found: {results_dir}", file=sys.stderr)
        return 1

    if weights is None:
        weights = {"plddt": 0.5, "iptm": 0.3, "ptm": 0.1, "pae": 0.1}

    designs = []

    # Search for confidence.json files
    for conf_file in results_path.rglob("confidence.json"):
        try:
            design = {"path": str(conf_file), "name": conf_file.parent.name if conf_file.parent != Path(".") else conf_file.stem}
            design.update(parse_confidence_json(conf_file))
            designs.append(design)
        except Exception as e:
            if verbose:
                print(f"Warning: Could not parse {conf_file}: {e}")

    # Search for PDB files (ESMFold/OmegaFold direct output)
    for pdb_file in results_path.rglob("*.pdb"):
        if any(x in pdb_file.name.lower() for x in ["design", "pred", "fold"]):
            plddt = parse_pdb_bfactor(pdb_file)
            if plddt is not None:
                designs.append({
                    "path": str(pdb_file),
                    "name": pdb_file.stem,
                    "plddt": plddt,
                })

    if not designs:
        print(f"ERROR: No valid results found in {results_dir}", file=sys.stderr)
        return 2

    # Apply filters
    passing = []
    for d in designs:
        if d.get("plddt", 100) < min_plddt:
            continue
        if "iptm" in d and d["iptm"] < min_iptm:
            continue
        if "ptm" in d and d["ptm"] < min_ptm:
            continue
        if "pae" in d and d["pae"] > max_pae:
            continue

        d["composite_score"] = compute_composite_score(d, weights)
        passing.append(d)

    # Sort by composite score
    passing.sort(key=lambda x: x.get("composite_score", x.get("plddt", 0)), reverse=True)

    if top_n:
        passing = passing[:top_n]

    # Output
    print(f"\n{'=' * 70}")
    print(f"Filtering Results: {len(passing)}/{len(designs)} designs passed")
    print(f"Criteria: pLDDT ≥ {min_plddt}, ipTM ≥ {min_iptm}, pTM ≥ {min_ptm}, PAE ≤ {max_pae}")
    print(f"{'=' * 70}")

    print(f"\n{'Rank':<6}{'Name':<25}{'pLDDT':<10}{'ipTM':<10}{'pTM':<10}{'Score':<10}")
    print("-" * 70)

    for i, d in enumerate(passing, 1):
        plddt = f"{d.get('plddt', 0):.1f}" if "plddt" in d else "N/A"
        iptm = f"{d.get('iptm', 0):.3f}" if "iptm" in d else "N/A"
        ptm = f"{d.get('ptm', 0):.3f}" if "ptm" in d else "N/A"
        score = f"{d.get('composite_score', 0):.1f}"
        print(f"{i:<6}{d['name']:<25}{plddt:<10}{iptm:<10}{ptm:<10}{score:<10}")

    # Save results
    output_file = results_path / "filtered_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_designs": len(designs),
            "passing_designs": len(passing),
            "criteria": {
                "min_plddt": min_plddt,
                "min_iptm": min_iptm,
                "min_ptm": min_ptm,
                "max_pae": max_pae,
            },
            "weights": weights,
            "top_designs": passing,
        }, f, indent=2)

    print(f"\nResults saved to: {output_file}")

    if verbose and len(passing) > 0:
        plddts = [d.get("plddt", 0) for d in passing if "plddt" in d]
        if plddts:
            print(f"\npLDDT Statistics:")
            print(f"  Mean: {mean(plddts):.1f}")
            print(f"  Best: {max(plddts):.1f}")
            print(f"  Worst: {min(plddts):.1f}")
            if len(plddts) > 1:
                print(f"  StdDev: {stdev(plddts):.1f}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Filter and rank protein designs by validation metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_filtering.py --results-dir outputs/validation/
  python run_filtering.py --results-dir outputs/validation/ --min-plddt 80 --min-iptm 0.75
  python run_filtering.py --results-dir outputs/validation/ --top-n 10 --verbose
        """
    )
    parser.add_argument("--results-dir", "-d", required=True,
                        help="Directory containing validation results")
    parser.add_argument("--min-plddt", type=float, default=70.0,
                        help="Minimum pLDDT threshold (default: 70)")
    parser.add_argument("--min-iptm", type=float, default=0.6,
                        help="Minimum ipTM threshold (default: 0.6)")
    parser.add_argument("--min-ptm", type=float, default=0.7,
                        help="Minimum pTM threshold (default: 0.7)")
    parser.add_argument("--max-pae", type=float, default=10.0,
                        help="Maximum PAE threshold (default: 10)")
    parser.add_argument("--top-n", type=int,
                        help="Only show top N designs")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output with statistics")

    args = parser.parse_args()

    return filter_designs(
        results_dir=args.results_dir,
        min_plddt=args.min_plddt,
        min_iptm=args.min_iptm,
        min_ptm=args.min_ptm,
        max_pae=args.max_pae,
        top_n=args.top_n,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
