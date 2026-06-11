---
name: error-recovery
description: Recover from failed protein design pipeline jobs and common errors without restarting the entire workflow
---

# Error Recovery Guide

**Pipeline jobs fail. This skill shows you how to recover quickly without losing progress.**

---

## Quick Recovery Checklist

When a stage fails, run through this checklist in order:

1. **Read the error message** — most failures fall into 5 categories
2. **Check disk space** — validation stages need 10–100 GB for outputs
3. **Check GPU memory** — OOM is the #1 cause of diffusion/validation failures
4. **Check input files** — PDB format issues, missing chains, wrong contig strings
5. **Retry with smaller batch** — reduce `num_designs`, `diffusion_batch_size`, or `subbatch_size`

---

## Common Failures and Fixes

### 1. Out of Memory (OOM)

**Symptoms:**
```
RuntimeError: CUDA out of memory
NCCL error: out of memory
```

**Fixes:**
```bash
# Reduce designs per batch
python scripts/run_rfdiffusion.py --contig "150-150" --num-designs 10  # was 50

# Reduce subbatch size for validation
python scripts/run_omegafold.py --subbatch-size 1

# Design shorter proteins
python scripts/run_rfdiffusion.py --contig "100-100"  # was 300-300

# Use CPU fallback for small validations
python scripts/run_omegafold.py --cpu
```

---

### 2. Tool Not Found / Conda Environment Missing

**Symptoms:**
```
FileNotFoundError: rfdiffusion not found
conda run: environment RFdiffusion not found
```

**Fixes:**
```bash
# Register the tool path
python scripts/run_rfdiffusion.py --configure

# Or set environment variable
export RFDIFFUSION_PATH=/path/to/RFdiffusion

# Or edit config
vim ~/.protein-design/config.yaml
```

See `config-management` skill for detailed configuration.

---

### 3. Invalid PDB / Preprocessing Failure

**Symptoms:**
```
PDBFixer failed: unknown atom
No heavy atoms found in chain A
Residue numbering is non-sequential
```

**Fixes:**
```bash
# Re-run PDBFixer with stricter repair
python scripts/run_pdbfixer.py --input broken.pdb --output fixed.pdb --add-atoms heavy

# Check for missing density / altlocs
python scripts/run_pdbfixer.py --input broken.pdb --output fixed.pdb --keep-heterogens none

# Visualize in PyMOL to spot missing loops
```

See `structure-preprocessing` skill.

---

### 4. Contig String Syntax Error

**Symptoms:**
```
Error parsing contig string
Invalid contig: B1-100/0 100-100
```

**Fixes:**
```bash
# Use quotes and proper Hydra syntax
python scripts/run_rfdiffusion.py \
  --contig "[B1-100/0 100-100]" \
  --num-designs 10

# For classic RFdiffusion (Hydra config):
./scripts/run_inference.py 'contigmap.contigs=[B1-100/0 100-100]'
```

See `structure-generation` skill for contig syntax.

---

### 5. Validation Crashes Mid-Run

**Symptoms:**
- AlphaFold3 stops after N designs
- `confidence.json` missing for some outputs
- MSA server timeout (MMseqs2)

**Fixes:**
```bash
# Resume by targeting only unvalidated designs
python scripts/run_alphafold3.py --json remaining.json --output-dir outputs/af3/

# Use local MSA instead of remote
python scripts/run_alphafold3.py --msa-mode local

# Switch to faster validator temporarily
python scripts/run_boltz.py --input remaining.fasta --output-dir outputs/boltz/
```

---

## Hook-Based Error Recovery

If hooks are installed (`python protein_design/hooks/install-hooks.py`), the `error-recovery.py` hook will:

- Detect common error patterns in tool outputs
- Suggest the most likely fix
- Recommend the next command to run
- Point you to the relevant skill

---

## Job-Level Recovery

For background jobs managed by `scripts/job_manager.py`:

```bash
# List failed jobs
python scripts/job_manager.py list

# Check logs
python scripts/job_manager.py tail <job_id> --lines 100

# Re-run a failed job
python scripts/job_manager.py resubmit <job_id>

# Cancel a hung job
python scripts/job_manager.py cancel <job_id>
```

---

## Stage-Specific Recovery

| Stage | Common Failure | Recovery Command |
|-------|---------------|------------------|
| 0. PDBFixer | Bad PDB format | Re-run with `--add-atoms heavy` |
| 1. RFdiffusion | OOM | Reduce `--num-designs` or contig length |
| 1. RFdiffusion3 | Missing checkpoint | `foundry install rfd3` |
| 2. ProteinMPNN | Too many sequences | Split FASTA and run batches |
| 3. AlphaFold3 | MSA timeout | Use `--msa-mode local` or switch to Boltz-1 |
| 3. Boltz-1 | Model download fails | Re-run with internet, check `~/.boltz` |
| 4. Filtering | Empty results | Lower `--min-plddt` threshold |

---

## Prevention Checklist

Before launching a long campaign:

- [ ] Run PDBFixer on all inputs
- [ ] Test one design end-to-end before batching
- [ ] Verify GPU has enough VRAM
- [ ] Ensure output directory has free disk space
- [ ] Confirm tool paths in `~/.protein-design/config.yaml`
- [ ] For AF3: verify databases are downloaded
- [ ] For HPC: test one job on cluster before full launch

---

## See Also

- `troubleshooting` — Broader troubleshooting guidance
- `config-management` — Tool path configuration
- `structure-preprocessing` — PDB repair details
- `install-guide` — Tool installation instructions
- `pipeline-selection` — Choose a more reliable pipeline
