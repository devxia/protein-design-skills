#!/usr/bin/env python3
"""
Standalone format converter.
Usage: python scripts/convert_format.py --from fasta --to af3-json --input seqs.fa --output af3_input.json

Supported conversions:
    fasta → alphafold3_json (AlphaFold3 input)
    fasta → boltz_yaml      (Boltz-1 input)
    fasta → chai_fasta      (Chai-1 input)
    csv   → fasta           (batch conversion)
    pdb   → fasta           (sequence extraction)
    json  → csv             (results summary)

Exit codes:
    0 = Success
    1 = Input file not found
    2 = Unsupported conversion
    3 = Conversion error
"""

import argparse
import csv
import json
import sys
from pathlib import Path


def read_fasta(filepath):
    """Read FASTA file and return list of (id, sequence) tuples."""
    sequences = []
    current_id = None
    current_seq = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_id is not None:
                    sequences.append((current_id, "".join(current_seq)))
                current_id = line[1:].split()[0]  # Take first word after >
                current_seq = []
            else:
                current_seq.append(line)

    if current_id is not None:
        sequences.append((current_id, "".join(current_seq)))

    return sequences


def write_fasta(sequences, filepath):
    """Write sequences to FASTA file."""
    with open(filepath, "w") as f:
        for seq_id, seq in sequences:
            f.write(f">{seq_id}\n")
            # Wrap at 60 characters
            for i in range(0, len(seq), 60):
                f.write(seq[i:i+60] + "\n")


def fasta_to_alphafold3_json(sequences, job_name="design", verbose=False):
    """Convert FASTA sequences to AlphaFold3 JSON input format."""
    af3_input = {
        "name": job_name,
        "sequences": [],
        "modelSeeds": [1],
    }

    for i, (seq_id, seq) in enumerate(sequences):
        chain_id = chr(65 + i) if i < 26 else f"X{i}"
        af3_input["sequences"].append({
            "protein": {
                "id": chain_id,
                "sequence": seq,
            }
        })

    return af3_input


def fasta_to_boltz_yaml(sequences, ligands=None, verbose=False):
    """Convert FASTA sequences to Boltz-1 YAML input format."""
    yaml_lines = ["sequences:"]

    for i, (seq_id, seq) in enumerate(sequences):
        chain_id = chr(65 + i) if i < 26 else f"X{i}"
        yaml_lines.append(f"  - protein:")
        yaml_lines.append(f"      id: {chain_id}")
        yaml_lines.append(f"      sequence: {seq}")

    if ligands:
        for ligand in ligands:
            yaml_lines.append(f"  - ligand:")
            yaml_lines.append(f"      id: {ligand['id']}")
            yaml_lines.append(f"      smiles: '{ligand['smiles']}'")

    return "\n".join(yaml_lines)


def fasta_to_chai_fasta(sequences, verbose=False):
    """Convert to Chai-1 compatible FASTA with entity comments."""
    lines = []
    for i, (seq_id, seq) in enumerate(sequences):
        lines.append(f">{seq_id}|protein")
        for j in range(0, len(seq), 60):
            lines.append(seq[j:j+60])
    return "\n".join(lines)


def csv_to_fasta(csv_path, id_col=0, seq_col=1, verbose=False):
    """Convert CSV to FASTA format."""
    sequences = []
    with open(csv_path) as f:
        reader = csv.reader(f)
        header = next(reader, None)  # Skip header
        for row in reader:
            if len(row) > max(id_col, seq_col):
                sequences.append((row[id_col], row[seq_col]))
    return sequences


def pdb_to_fasta(pdb_path, verbose=False):
    """Extract sequences from PDB file."""
    try:
        from Bio import PDB
        structure = PDB.PDBParser(QUIET=True).get_structure("x", pdb_path)

        sequences = []
        for model in structure:
            for chain in model:
                residues = []
                for residue in chain:
                    if residue.id[0] == " ":  # Standard amino acid
                        resname = residue.resname
                        # Convert 3-letter to 1-letter
                        aa_map = {
                            "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E",
                            "PHE": "F", "GLY": "G", "HIS": "H", "ILE": "I",
                            "LYS": "K", "LEU": "L", "MET": "M", "ASN": "N",
                            "PRO": "P", "GLN": "Q", "ARG": "R", "SER": "S",
                            "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
                        }
                        one_letter = aa_map.get(resname, "X")
                        residues.append(one_letter)

                if residues:
                    seq = "".join(residues)
                    chain_id = chain.id
                    sequences.append((f"{Path(pdb_path).stem}_chain_{chain_id}", seq))

        return sequences
    except ImportError:
        print("ERROR: BioPython required for PDB conversion. Install: pip install biopython", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: Could not parse PDB: {e}", file=sys.stderr)
        return None


def json_results_to_csv(results_dir, output_csv, verbose=False):
    """Summarize validation results to CSV."""
    import statistics

    results_path = Path(results_dir)
    rows = []

    for conf_file in results_path.rglob("confidence.json"):
        try:
            with open(conf_file) as f:
                data = json.load(f)

            row = {"name": conf_file.parent.name}
            for key in ["plddt", "ptm", "iptm", "pae"]:
                if key in data:
                    row[key] = data[key]
            rows.append(row)
        except Exception:
            pass

    if not rows:
        print(f"ERROR: No valid results found in {results_dir}", file=sys.stderr)
        return None

    # Write CSV
    fieldnames = ["name", "plddt", "iptm", "ptm", "pae"]
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return output_csv


def convert_format(from_fmt, to_fmt, input_path, output_path, job_name="design",
                   ligands=None, verbose=False):
    """Main conversion dispatcher."""
    input_path = Path(input_path)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 1

    conversion_key = f"{from_fmt.lower()}→{to_fmt.lower()}"

    try:
        if conversion_key in ["fasta→alphafold3_json", "fasta→af3-json", "fasta→af3"]:
            sequences = read_fasta(input_path)
            result = fasta_to_alphafold3_json(sequences, job_name, verbose)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)

        elif conversion_key in ["fasta→boltz_yaml", "fasta→boltz-yaml", "fasta→boltz"]:
            sequences = read_fasta(input_path)
            result = fasta_to_boltz_yaml(sequences, ligands, verbose)
            with open(output_path, "w") as f:
                f.write(result)

        elif conversion_key in ["fasta→chai_fasta", "fasta→chai-fasta", "fasta→chai"]:
            sequences = read_fasta(input_path)
            result = fasta_to_chai_fasta(sequences, verbose)
            with open(output_path, "w") as f:
                f.write(result)

        elif conversion_key in ["csv→fasta", "csv→fasta"]:
            sequences = csv_to_fasta(input_path, verbose=verbose)
            write_fasta(sequences, output_path)

        elif conversion_key in ["pdb→fasta"]:
            sequences = pdb_to_fasta(input_path, verbose)
            if sequences is None:
                return 3
            write_fasta(sequences, output_path)

        elif conversion_key in ["json→csv", "json_results→csv"]:
            result = json_results_to_csv(input_path, output_path, verbose)
            if result is None:
                return 2

        else:
            print(f"ERROR: Unsupported conversion: {from_fmt} → {to_fmt}", file=sys.stderr)
            print(f"Supported: fasta→alphafold3_json, fasta→boltz_yaml, fasta→chai_fasta, csv→fasta, pdb→fasta, json→csv", file=sys.stderr)
            return 2

        if verbose:
            print(f"SUCCESS: Converted {input_path} → {output_path}")
            print(f"Format: {from_fmt} → {to_fmt}")

        return 0

    except Exception as e:
        print(f"ERROR: Conversion failed: {e}", file=sys.stderr)
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Convert between protein design file formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # FASTA to AlphaFold3 JSON
  python convert_format.py --from fasta --to alphafold3_json --input seqs.fa --output af3.json --job-name my_design

  # FASTA to Boltz-1 YAML
  python convert_format.py --from fasta --to boltz_yaml --input seqs.fa --output boltz.yaml

  # PDB to FASTA (sequence extraction)
  python convert_format.py --from pdb --to fasta --input structure.pdb --output seqs.fa

  # Validation results to CSV summary
  python convert_format.py --from json --to csv --input outputs/validation/ --output results.csv
        """
    )
    parser.add_argument("--from", "-f", dest="from_fmt", required=True,
                        help="Source format: fasta, pdb, csv, json")
    parser.add_argument("--to", "-t", dest="to_fmt", required=True,
                        help="Target format: alphafold3_json, boltz_yaml, chai_fasta, fasta, csv")
    parser.add_argument("--input", "-i", required=True,
                        help="Input file or directory")
    parser.add_argument("--output", "-o", required=True,
                        help="Output file")
    parser.add_argument("--job-name", default="design",
                        help="Job name for AlphaFold3 JSON (default: design)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return convert_format(
        from_fmt=args.from_fmt,
        to_fmt=args.to_fmt,
        input_path=args.input,
        output_path=args.output,
        job_name=args.job_name,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
