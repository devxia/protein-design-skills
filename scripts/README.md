# Standalone Execution Scripts

These scripts provide direct CLI-based execution for all protein design pipeline stages.

## Scripts

| Script | Purpose |
|--------|---------|
| `run_pdbfixer.py` | PDB preprocessing (Stage 0) |
| `run_rfdiffusion.py` | Backbone generation (Stage 1) |
| `run_proteinmpnn.py` | Sequence design (Stage 2) |
| `run_alphafold3.py` | Structure validation — best accuracy (Stage 3) |
| `run_boltz.py` | Boltz-1 validation — MIT license, complexes |
| `run_chai1.py` | Chai-1 validation — Apache 2.0, constraints |
| `run_omegafold.py` | OmegaFold validation — fast, no databases needed |
| `run_esmfold.py` | ESMFold validation — fastest |
| `run_protenix.py` | Protenix validation — training + inference |
| `run_openfold3.py` | OpenFold3 validation — pip install, AF3 reimplementation |
| `run_filtering.py` | Result filtering and ranking (Stage 4) |
| `convert_format.py` | File format conversion |
| `job_manager.py` | Background job tracking |
| `batch_runner.py` | Chain multiple pipeline stages |
| `summarize_outputs.py` | Progress summary + quality report |
| `project_dashboard.py` | Project-wide dashboard with stage progress |

**Total: 16 scripts** — All major pipeline stages + job management + progress reporting covered.

## Design Principles

1. **CLI-first**: All scripts accept command-line arguments
2. **Config-aware**: Read tool paths from `~/.protein-design/config.yaml`
3. **History logging**: Write execution records to `~/.protein-design/history.jsonl`
4. **Proper exit codes**: 0=success, 1-4=various errors
5. **Verbose mode**: `--verbose` flag for detailed output
6. **Auto-detection**: Find tools in conda envs, common paths, or PATH

## Usage Pattern

```bash
# Run RFdiffusion directly
python scripts/run_rfdiffusion.py \
    --contig "150-150" \
    --num-designs 50 \
    --output-prefix outputs/design \
    --verbose
```

## Progress Monitoring

Track pipeline progress and summarize outputs at any stage:

```bash
# One-shot summary of artifact counts and quality metrics
python scripts/summarize_outputs.py --output-dir outputs/

# Live progress watch (refreshes every 30s)
python scripts/summarize_outputs.py --output-dir outputs/ --watch

# With expected counts for progress bars
python scripts/summarize_outputs.py --output-dir outputs/ \
  --expected-backbones 50 \
  --expected-sequences 200 \
  --expected-validations 50

# Machine-readable JSON for downstream automation
python scripts/summarize_outputs.py --output-dir outputs/ --json
```

### Project-Wide Dashboard

For a multi-stage overview across an entire design campaign:

```bash
# One-shot project dashboard
python scripts/project_dashboard.py --output-dir outputs/

# With expected counts for progress bars
python scripts/project_dashboard.py --output-dir outputs/ \
  --expected-backbones 50 \
  --expected-sequences 400 \
  --expected-validations 50

# Live watch mode (refreshes every 30s)
python scripts/project_dashboard.py --output-dir outputs/ --watch
```

The dashboard shows:
- Overall artifact counts across all discovered stages
- Per-stage progress bars against expected targets
- Mean / best / worst pLDDT and ipTM
- Quality distribution (Excellent/Good/Acceptable/Poor)
- Next-step recommendation based on which stages are missing

## Pipeline Example

```bash
# Stage 0: Preprocess
python scripts/run_pdbfixer.py --input target.pdb --output target_fixed.pdb

# Stage 1: Generate backbones
python scripts/run_rfdiffusion.py \
    --input-pdb target_fixed.pdb \
    --contig "[B1-100/0 100-100]" \
    --num-designs 50

# Stage 2: Design sequences
python scripts/run_proteinmpnn.py \
    --pdb-path "outputs/design_*.pdb" \
    --out-folder outputs/seqs/ \
    --num-seq 8

# Stage 3a: Convert format
python scripts/convert_format.py \
    --from fasta --to alphafold3_json \
    --input outputs/seqs/seqs.fa \
    --output af3_input.json

# Stage 3b: Validate
python scripts/run_alphafold3.py \
    --json af3_input.json \
    --output-dir outputs/af3/

# Stage 4: Filter
python scripts/run_filtering.py \
    --results-dir outputs/af3/ \
    --min-plddt 75 \
    --top-n 10
```

## Configuration

Scripts read configuration from (in order):
1. Environment variables (`RFDIFFUSION_PATH`, `PROTEINMPNN_PATH`, etc.)
2. `~/.protein-design/config.yaml`
3. `~/.kimi-protein-design/config.yaml` (legacy)
4. Auto-detection (common paths, conda envs)

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Input file not found |
| 2 | Tool not installed / not found |
| 3 | Execution error |
| 4 | Invalid arguments |

## Stage 3 Validation Alternatives

All Stage 3 validation tools are supported as standalone scripts:

| Speed | Script | Best For |
|-------|--------|----------|
| **Slowest** | `run_alphafold3.py` | Best accuracy, full MSA |
| **Medium** | `run_boltz.py` | MIT license, complexes |
| **Medium** | `run_chai1.py` | Apache 2.0, constraints |
| **Fast** | `run_omegafold.py` | No databases needed |
| **Fastest** | `run_esmfold.py` | Ultra-fast screening |
| **Training** | `run_protenix.py` | Training + inference scaling |
| **Open source** | `run_openfold3.py` | pip install, AF3 reimplementation |

### Two-Stage Validation Strategy

For screening many designs (100+):

```bash
# Stage 3a: Fast screen with ESMFold
python scripts/run_esmfold.py -i sequences.fasta -o outputs/esmfold/

# Stage 3b: Validate top 20 with AlphaFold3
python scripts/convert_format.py --from fasta --to alphafold3_json -i top20.fa -o top20.json
python scripts/run_alphafold3.py -j top20.json -o outputs/af3_top20/
```

**Time savings**: 100 designs × 30 min (AF3) = 50 hours
vs. 100 designs × 10 sec (ESMFold) + 20 designs × 30 min (AF3) = ~1.5 hours

## Job Management

### Background Execution with job_manager.py

```bash
# Submit a background job
JOB_ID=$(python scripts/job_manager.py submit --name rfdiff -- \
  python scripts/run_rfdiffusion.py --contig "150-150" --num-designs 50)

# Check status
python scripts/job_manager.py status $JOB_ID

# Tail log
python scripts/job_manager.py tail $JOB_ID --lines 50

# Wait for completion
python scripts/job_manager.py wait $JOB_ID --timeout 3600

# Cancel if needed
python scripts/job_manager.py cancel $JOB_ID
```

### Batch Pipeline with batch_runner.py

```bash
# Run complete pipeline with one command
python scripts/batch_runner.py \
  --input-pdb target.pdb \
  --contig "[B1-100/0 100-100]" \
  --validator omegafold \
  --num-designs 50 \
  --verbose

# Or from config file
python scripts/batch_runner.py --config pipeline.yaml
```

## All Scripts Reference

See [API Reference — Scripts](../docs/en/api-reference/scripts.md) for complete parameter documentation for all 16 scripts.
