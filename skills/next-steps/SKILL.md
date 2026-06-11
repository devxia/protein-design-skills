---
name: next-steps
description: Decide what command to run next at any point in the protein design pipeline based on completed stages and current outputs
---

# Next Steps Guide

**Stuck wondering what to run next? This skill maps your current pipeline state to the exact next command.**

---

## Quick State-to-Command Map

| If you see these files... | Your stage | Next command |
|---------------------------|------------|--------------|
| Nothing yet | Not started | `python scripts/run_pdbfixer.py --input target.pdb --output target_fixed.pdb` |
| `*_fixed.pdb` or `preprocessed/*.pdb` | Stage 0 complete | `python scripts/run_rfdiffusion.py --input-pdb target_fixed.pdb --contig "150-150" --num-designs 50` |
| `backbones/*.pdb` | Stage 1 complete | `python scripts/run_proteinmpnn.py --pdb-path "backbones/*.pdb" --out-folder outputs/seqs/ --num-seq 8` |
| `seqs/*.fa` or `seqs/*.fasta` | Stage 2 complete | `python scripts/convert_format.py --from fasta --to alphafold3_json --input outputs/seqs/seqs.fa --output outputs/af3_input.json` |
| `af3_input.json` | Stage 2.5 ready | `python scripts/run_alphafold3.py --json outputs/af3_input.json --output-dir outputs/af3/` |
| `af3/*/confidence.json` or `*.cif` | Stage 3 complete | `python scripts/run_filtering.py --results-dir outputs/af3/ --min-plddt 75 --top-n 10` |
| `filtered/*.csv` or ranking files | Stage 4 complete | `python scripts/summarize_outputs.py --output-dir outputs/` |

---

## How to Check Your Current State

### One-shot check

```bash
python scripts/summarize_outputs.py --output-dir outputs/
```

This tells you:
- How many PDB, FASTA, and CIF files exist
- How many `confidence.json` files (validation completions)
- Mean / best pLDDT and ipTM
- Quality distribution (Excellent/Good/Acceptable/Poor)

### Live dashboard

```bash
python scripts/project_dashboard.py --output-dir outputs/
```

This adds:
- Stage-by-stage progress bars
- Next-step recommendation
- Top designs ranked by pLDDT

---

## Stage-by-Stage Next Steps

### After Stage 0: Preprocessing

**You have:** a fixed PDB (`target_fixed.pdb`)

**Choose Stage 1 based on your goal:**

| Goal | Stage 1 Tool | Command |
|------|--------------|---------|
| General protein / binder | RFdiffusion | `python scripts/run_rfdiffusion.py --input-pdb target_fixed.pdb --contig "150-150" --num-designs 50` |
| All-atom ligand/DNA/RNA/enzyme | RFdiffusion3 | `rfd3 design out_dir=outputs/rfd3 inputs=config.yaml ckpt_path=...` |
| Unconditional diverse backbones | TopoDiff | `python run_sampling.py -o outputs/topodiff -s 100 -e 120 -n 10 -m all_round` |
| Ellipsoid layout control | ProtComposer | `python sample.py --outdir outputs/protcomposer --num_blobs 9 ...` |
| Natural language design | Chroma | Follow `chroma-backbone` skill |

### After Stage 1: Backbone Generation

**You have:** backbone PDB files (`outputs/backbones/*.pdb`)

**Choose Stage 2 based on your goal:**

| Goal | Stage 2 Tool | Command |
|------|--------------|---------|
| General sequence design | ProteinMPNN | `python scripts/run_proteinmpnn.py --pdb-path "outputs/backbones/*.pdb" --out-folder outputs/seqs/ --num-seq 8` |
| Ligand-aware sequences | LigandMPNN | `python scripts/run_ligandmpnn.py --pdb-path ... --out-folder ...` |
| Fitness-conditional optimization | PRO-LDM | `python main.py --mode sample --dataset YOUR_DATASET --dif_sample_label 1 ...` |
| Partial masking / variant scoring | ESM-IF1 | Follow `esm-if1-design` skill |

### After Stage 2: Sequence Design

**You have:** FASTA files (`outputs/seqs/*.fa`)

**Next:** convert to the input format your validator needs.

```bash
# For AlphaFold3
python scripts/convert_format.py \
  --from fasta --to alphafold3_json \
  --input outputs/seqs/seqs.fa \
  --output outputs/af3_input.json
```

### After Stage 2.5: Format Conversion

**You have:** `af3_input.json` (or equivalent)

**Choose Stage 3 based on speed/accuracy needs:**

| Speed | Validator | Command |
|-------|-----------|---------|
| Slowest, best accuracy | AlphaFold3 | `python scripts/run_alphafold3.py --json outputs/af3_input.json --output-dir outputs/af3/` |
| Medium, MIT license, complexes | Boltz-1 | `python scripts/run_boltz.py --input outputs/seqs/seqs.fa --output-dir outputs/boltz/` |
| Medium, Apache 2.0 | Chai-1 | `python scripts/run_chai1.py ...` |
| Fast, no DB | OmegaFold | `python scripts/run_omegafold.py --input outputs/seqs/seqs.fa --output-dir outputs/omegafold/` |
| Fastest | ESMFold | `python scripts/run_esmfold.py --input outputs/seqs/seqs.fa --output-dir outputs/esmfold/` |

### After Stage 3: Validation

**You have:** predicted structures + `confidence.json` files

**Next:** filter and rank.

```bash
python scripts/run_filtering.py \
  --results-dir outputs/af3/ \
  --min-plddt 75 \
  --min-iptm 0.6 \
  --top-n 10
```

### After Stage 4: Filtering

**You have:** ranked designs (`outputs/filtered/` or summary CSV)

**Next:** generate final report.

```bash
python scripts/summarize_outputs.py --output-dir outputs/
python scripts/project_dashboard.py --output-dir outputs/
```

---

## Common Branching Decisions

### Should I validate with AlphaFold3 or a faster tool?

- **≤50 designs, need best accuracy** → AlphaFold3
- **100+ designs, need quick screen** → ESMFold or OmegaFold first, then AlphaFold3 on top 10–20
- **Protein-ligand / DNA / RNA complex** → RFAA or Boltz-1
- **Commercial project** → Boltz-1 or Chai-1

### Should I use RFdiffusion or RFdiffusion3 for Stage 1?

- **Proteins only, no ligands/DNA/RNA** → RFdiffusion (faster setup)
- **Ligands, DNA, RNA, metals, enzymes** → RFdiffusion3
- **Want training/fine-tuning code** → RFdiffusion3

### Should I add an ensemble Stage 2?

If you have compute budget and this is a high-value target, run both:
1. ProteinMPNN
2. ESM-IF1 (for variants / partial masking)
3. PRO-LDM (if you have fitness labels)

Then merge and deduplicate sequences before validation.

---

## What If a Stage Fails?

See `error-recovery` skill for detailed fixes.

Quick map:

| Symptom | Likely Fix |
|---------|------------|
| `CUDA out of memory` | Reduce `--num-designs` or contig length |
| `Tool not found` | Configure paths in `~/.protein-design/config.yaml` |
| `Invalid PDB` | Re-run `run_pdbfixer.py` with `--add-atoms heavy` |
| `MSA timeout` (AF3) | Switch to Boltz-1 / Chai-1 / OmegaFold |
| `Empty filtering results` | Lower `--min-plddt` to 70 or 65 |

---

## Automation

If hooks are installed, you will receive automatic stage-complete summaries and next-step hints after each stage. To install:

```bash
python protein_design/hooks/install-hooks.py
```

The hooks that help with next steps:
- `progress-reporter.py` — summarizes outputs after each tool completes
- `progress-query-helper.py` — answers "what's the status?" questions
- `pipeline-orchestrator.py` — suggests full pipeline commands

---

## See Also

- `periodic-summary` — Set up regular progress checks
- `error-recovery` — Recover from failed stages
- `pipeline-selection` — Choose the right workflow for your goal
- `quickstart-guide` — Get started with your first design
