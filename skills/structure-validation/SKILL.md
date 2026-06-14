---
name: structure-validation
description: Structure prediction and validation with AlphaFold3 and alternatives (Stage 3)
---

# Stage 3: Structure Validation (AlphaFold3 + Alternatives)

**This skill is used AFTER sequence design (Stage 2).**

**Quick entry:** If you have designed sequences and need to predict/check their 3D structures, you are in the right place.

**Typical flow:** `structure-generation` (Stage 1) → `sequence-design` (Stage 2) → **THIS SKILL** (Stage 3) → `filtering-ranking` (Stage 4)

**Alternative validators (no AF3 databases needed):**
- Fast + no DB: `omegafold-validation`, `esmfold-validation`
- Commercial license: `boltz-validation` (MIT), `chai1-validation` (Apache 2.0)
- Multiple validators: `cross-validation`

## When to Use This Skill

- You have sequences from ProteinMPNN and need structure prediction
- You want pLDDT, pTM, ipTM confidence metrics
- You need to validate binder-target complexes
- You want to extract structure embeddings
- You need no-MSA fast screening

**Not sure which validator to use?** Read `pipeline-selection` for the comparison table.

## AlphaFold3 Overview

AlphaFold3 predicts 3D protein structures from sequence input. In the design pipeline, it's used to validate that sequences designed by ProteinMPNN actually fold into the intended backbone structure.

## Input Format

AlphaFold3 accepts a JSON file. For protein-only designs:

```json
{
  "name": "my_design",
  "modelSeeds": [1],
  "sequences": [
    {
      "protein": {
        "id": "A",
        "sequence": "MKTLLILTGLVAGES...",
        "modifications": []
      }
    }
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### Multi-Chain Complex
```json
{
  "name": "binder_complex",
  "sequences": [
    {"protein": {"id": "A", "sequence": "TARGETSEQ...", "modifications": []}},
    {"protein": {"id": "B", "sequence": "BINDERSEQ...", "modifications": []}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### With Ligand
```json
{
  "name": "protein_ligand",
  "sequences": [
    {"protein": {"id": "A", "sequence": "MKTLLILTGL...", "modifications": []}},
    {"ligand": {"id": "B", "ccdCodes": ["ATP"]}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### With DNA
```json
{
  "name": "protein_dna",
  "sequences": [
    {"protein": {"id": "A", "sequence": "MKTLLILTGL...", "modifications": []}},
    {"dna": {"id": "B", "sequence": "GCTAGC"}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### With RNA
```json
{
  "name": "protein_rna",
  "sequences": [
    {"protein": {"id": "A", "sequence": "MKTLLILTGL...", "modifications": []}},
    {"rna": {"id": "B", "sequence": "GCUAGC"}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

## Standalone Script

```bash
python scripts/run_alphafold3.py \
  --json inputs/design_af3_input.json \
  --output-dir outputs/af3 \
  --db-dir /path/to/databases \
  --num-seeds 1 \
  --num-samples 1
```

To skip MSA for faster inference:

```bash
python scripts/run_alphafold3.py \
  --json inputs/design_af3_input.json \
  --output-dir outputs/af3_fast \
  --no-msa \
  --num-seeds 1 \
  --num-samples 1
```

## Parameters

| Parameter | CLI Flag | Required | Default | Description |
|-----------|----------|----------|---------|-------------|
| `json_path` | `--json` / `-j` | ✅ | — | Input JSON file path |
| `output_dir` | `--output-dir` / `--out-dir` / `-o` | ✅ | — | Output directory |
| `db_dir` | `--db-dir` / `-d` | ❌ | auto-detected | Genetic databases directory |
| `num_seeds` | `--num-seeds` | ❌ | 1 | Number of random seeds |
| `num_samples` | `--num-samples` | ❌ | 1 | Samples per seed |
| `no_msa` | `--no-msa` | ❌ | false | Skip MSA search (faster, no databases) |
| `verbose` | `--verbose` / `-v` | ❌ | false | Verbose output |

## Database Setup

AlphaFold3 requires **genetic databases** (~2.6TB) for MSA search. The plugin handles this automatically:

| Scenario | Behavior |
|----------|----------|
| `--db-dir` passed explicitly | Uses the provided path |
| `db_dir` set in `~/.protein-design/config.yaml` | Uses the configured path |
| `~/public_databases` exists and looks valid | Auto-detected |
| No databases found + default run | Logs warning, MSA may fail |
| No databases found + `--no-msa` | Skips MSA, runs inference only |

**To configure databases:**

Edit `~/.protein-design/config.yaml`:
```yaml
db_dir: /data/public_databases
```

Or set the environment variable:
```bash
export PROTEIN_DESIGN_DB_DIR=/data/public_databases
```

**To check database status:**
```bash
python protein_design/hooks/session-health-check.py
# Or inspect manually:
ls -d ~/public_databases 2>/dev/null && echo "Found" || echo "Missing"
```

## Format Conversion (Stage 2 → Stage 3)

ProteinMPNN outputs FASTA; AlphaFold3 needs JSON. Use `convert_format`:

```bash
python scripts/convert_format.py \
  --from fasta \
  --to alphafold3_json \
  --input seqs/design_0.fa \
  --job-name design_0 \
  --seed 1 \
  --output seqs/design_0_af3_input.json
```

### Multi-Chain Conversion (Binder + Target)

For binder-target complexes, provide the receptor PDB:

```bash
python scripts/convert_format.py \
  --from fasta \
  --to alphafold3_json \
  --input seqs/binder.fa \
  --job-name binder_complex \
  --seed 1 \
  --receptor-pdb target_fixed.pdb \
  --receptor-chain A \
  --output seqs/binder_complex_af3_input.json
```

## Output Format

```
my_design/
├── my_design_model.cif              # Top-ranked structure (mmCIF)
├── my_design_confidences.json       # Full confidence data
├── my_design_summary_confidences.json  # Summary metrics
├── my_design_data.json              # Input + MSA data
├── my_design_ranking_scores.csv     # All predictions ranked
└── seed-1_sample-0/                 # Individual predictions
    ├── ...
```

## Confidence Metrics & Thresholds

| Metric | Range | Acceptable | Good | Excellent |
|--------|-------|------------|------|-----------|
| **pLDDT** | 0–100 | >70 | >80 | >90 |
| **pTM** | 0–1 | >0.5 | >0.7 | >0.9 |
| **ipTM** | 0–1 | >0.6 | >0.8 | >0.9 |
| **ranking_score** | [-100, 1.5] | Higher is better | — | — |
| **has_clash** | bool | false | false | false |

### Metric Interpretations

- **pLDDT**: Per-atom confidence. High values = well-defined structure.
- **pTM**: Overall topology confidence. >0.7 indicates correct fold likely.
- **ipTM**: Interface confidence (critical for binder design). >0.8 = strong interface.
- **has_clash**: True if severe atomic clashes detected. Reject these designs.

### Per-Chain Metrics

For multi-chain complexes, AlphaFold3 outputs per-chain pLDDT and pTM:
- `chain_ptm`: Per-chain topology confidence
- `chain_iptm`: Per-chain interface confidence
- `per_chain_plddt`: Average pLDDT per chain

## Advanced Features

### Embedding Extraction

Saving structure embeddings is not exposed by the `run_alphafold3.py` wrapper. To extract embeddings, invoke the AlphaFold3 inference pipeline directly with the appropriate output settings.

Embeddings can be used for:
- Clustering designs by structural similarity
- Training downstream classifiers
- Transfer learning

### Distogram Saving

Saving predicted distance distributions is not exposed by the `run_alphafold3.py` wrapper. To save distograms, invoke the AlphaFold3 inference pipeline directly.

### No-MSA Fast Inference

Skip MSA for rapid screening (less accurate):

```bash
python scripts/run_alphafold3.py \
  --json inputs/design.json \
  --output-dir outputs/af3_fast \
  --no-msa \
  --num-seeds 1 \
  --num-samples 1
```

Useful for:
- Initial screening of many designs
- When databases are not available
- Proteins similar to training data

## Result Analysis

### Analyze Without Re-running

Parse existing AlphaFold3 output:

```bash
# One-shot summary for a single design directory
python scripts/summarize_outputs.py --output-dir outputs/af3/design_0

# Or parse confidence JSON directly with Python
python -c "
import json
with open('outputs/af3/design_0/design_0_summary_confidences.json') as f:
    data = json.load(f)
print('pLDDT:', data.get('plddt'))
print('pTM:', data.get('ptm'))
print('ipTM:', data.get('iptm'))
print('ranking_score:', data.get('ranking_score'))
print('has_clash:', data.get('has_clash'))
"
```

Returns:
- pLDDT, pTM, ipTM
- Per-chain metrics
- Ranking scores
- Clash status
- Best structure path

## Typical Runtime

| Protein Size | With MSA | MSA Precomputed | No-MSA |
|-------------|----------|-----------------|--------|
| <200 aa | 5–30 min | 2–10 min | 1–5 min |
| 200–500 aa | 30–90 min | 10–30 min | 5–15 min |
| >500 aa | 1–3 hours | 30–60 min | 15–30 min |

## Workflow

```
Input: FASTA from Stage 2 (ProteinMPNN)
     ↓
python scripts/convert_format.py --from fasta --to alphafold3_json ...
     ↓
python scripts/run_alphafold3.py --json ... --output-dir ...
     ↓
Track progress with python scripts/summarize_outputs.py --output-dir outputs/af3
     ↓
Parse metrics (pLDDT, ipTM, pTM)
     ↓
Return: mmCIF + confidence JSON → Stage 4 (filtering)
```

## Batch Validation Optimization

For >10 designs, avoid blocking the session:

```bash
# Watch output directory automatically
python scripts/summarize_outputs.py \
  --output-dir outputs/af3 \
  --expected-validations 50 \
  --watch \
  --interval 60
```

Or schedule a periodic check:
```
/loop 10m Check AlphaFold3 batch progress in outputs/af3/. Report total completed, count with pLDDT>80 and ipTM>0.75, and any failures.
```

Stop the loop when the batch is complete.

## Alternative Validation Tools

### ESMFold (Fast, No MSA)
- Single-sequence prediction using ESM-2 embeddings
- 5-30 seconds per protein
- Good for initial screening
- See `fast-screening` skill for details

### ColabFold (Faster MSA)
- Uses MMseqs2 instead of jackhmmer/HHblits
- ~100GB database vs ~2.6TB
- Good speed/accuracy tradeoff
- See `fast-screening` skill for details

### Boltz-2 (Structure + Affinity)
- Predicts structures AND binding affinity
- Useful for ligand-binding designs
- See `fast-screening` skill for details

## Tips

- Skip MSA (`run_data_pipeline=false`) if re-running with precomputed data
- For binder validation, ipTM is the most important metric
- pLDDT > 80 and ipTM > 0.8 is a good initial filter
- Always check `has_clash` — clashes indicate physically impossible structures
- For embedding extraction, invoke AlphaFold3 directly; the wrapper does not expose this flag
- For multimer complexes, check per-chain pLDDT for all chains
- `scripts/summarize_outputs.py` can parse outputs without re-running

## AlphaFold3 Not Installed?

You have many alternatives — **no databases required** for any of these:

| Alternative | Install | GPU | Databases | Speed | License |
|-------------|---------|-----|-----------|-------|---------|
| ESMFold | `pip install fair-esm` | Optional | None | ~2s/seq | MIT |
| OmegaFold | `pip install omegafold` | Yes | None | ~5s/seq | MIT |
| Boltz-1 | `pip install boltz` | Yes | None | ~10s/seq | MIT |
| Boltz-2 | `pip install boltz` | Yes | None | ~10s/seq | MIT |
| Chai-1 | See chai-1 docs | Yes | None | ~10s/seq | Apache 2.0 |
| OpenFold3 | `pip install openfold3` | Yes | None | ~15s/seq | Apache 2.0 |
| Protenix | See protenix docs | Yes | None | ~15s/seq | MIT |

**Quick start with ESMFold (easiest, CPU-compatible):**
```bash
pip install fair-esm
python scripts/run_esmfold.py --input outputs/seqs/seqs.fa --output-dir outputs/validation/ --verbose
```

**Quick start with OmegaFold (fast, GPU required):**
```bash
pip install omegafold
python scripts/run_omegafold.py --input outputs/seqs/seqs.fa --output-dir outputs/validation/ --verbose
```

**Quick start with Boltz-1 (MIT license, good for complexes):**
```bash
pip install boltz
python scripts/run_boltz.py --input outputs/seqs/seqs.fa --out-dir outputs/validation/ --verbose
```

See `install-guide` skill for full AlphaFold3 installation instructions.
