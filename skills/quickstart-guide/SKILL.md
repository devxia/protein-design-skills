---
name: quickstart-guide
description: Zero-to-first-design quick start guide — the fastest way to go from nothing to your first protein design
---

# Quick Start Guide: Your First Protein Design

**New to this plugin? Start here. This is the fastest path from zero to a designed protein.**

## Step 0: Install (5 minutes)

```bash
# Clone the repo
git clone https://github.com/devxia/protein-design-skills.git
cd protein-design-skills

# Install Python dependencies
pip install biopython pyyaml

# Install hooks (auto-detects your agent)
python protein_design/hooks/install-hooks.py
```

## Step 1: Install External Tools (30-60 minutes)

The plugin orchestrates external ML tools. You need to install them separately.

### Minimum Setup (3 tools for a complete pipeline)

| Stage | Tool | Install | Notes |
|-------|------|---------|-------|
| 0 | PDBFixer | `conda install -c conda-forge pdbfixer openmm` | Required for PDB repair |
| 1 | RFdiffusion | `git clone https://github.com/RosettaCommons/RFdiffusion.git` | Backbone generation |
| 2 | ProteinMPNN | `git clone https://github.com/dauparas/ProteinMPNN.git` | Sequence design |
| 3 | **Pick ONE validator** | See below | Structure validation |

### Stage 3 Validator — Pick One

| Validator | Install | Databases | Speed | Best For |
|-----------|---------|-----------|-------|----------|
| **ESMFold** | `pip install esmfold` | None | Fastest (~2s/seq) | Quick screening |
| **OmegaFold** | `pip install omegafold` | None | Fast (~5s/seq) | No-database validation |
| **Boltz-1** | `pip install boltz` | None | Medium | MIT license, complexes |
| **Chai-1** | `pip install chai-lab` | None | Medium | Apache 2.0, constraints |
| AlphaFold3 | git clone + 2.6TB DB | 2.6TB | Slow (~30min) | Best accuracy |

**No databases?** Start with ESMFold or OmegaFold — they work out of the box.

### Quick Install Commands

```bash
# Minimal setup (PDBFixer + ESMFold, works immediately)
conda install -c conda-forge pdbfixer openmm
pip install esmfold

# Full setup (all 3 stages)
git clone https://github.com/RosettaCommons/RFdiffusion.git
cd RFdiffusion && conda env create -f env/SE3nv.yml && conda activate SE3nv && pip install -e .

git clone https://github.com/dauparas/ProteinMPNN.git
cd ProteinMPNN && conda create -n proteinmpnn python=3.9 && conda activate proteinmpnn && pip install torch numpy

conda install -c conda-forge pdbfixer openmm
pip install omegafold  # or esmfold for fastest
```

See `install-guide` skill for detailed installation instructions.

## Step 2: Run Your First Design (5 minutes)

### Design 1: Unconditional Monomer (simplest)

```bash
# Generate a 150-residue protein backbone
python scripts/run_rfdiffusion.py \
    --contig "150-150" \
    --num-designs 10 \
    --output-prefix outputs/monomer/design \
    --verbose

# Design sequences for the backbones
python scripts/run_proteinmpnn.py \
    --pdb-path "outputs/monomer/design_*.pdb" \
    --out-folder outputs/monomer/seqs/ \
    --num-seq 8 \
    --verbose

# Validate with OmegaFold (no databases needed)
python scripts/run_omegafold.py \
    --input outputs/monomer/seqs/seqs.fa \
    --output-dir outputs/monomer/validation/ \
    --verbose

# Filter top designs
python scripts/run_filtering.py \
    --results-dir outputs/monomer/validation/ \
    --min-plddt 75 \
    --top-n 5 \
    --verbose
```

### Design 2: Binder for a Target (one-liner with batch runner)

```bash
# Create a pipeline config
cat > binder_pipeline.yaml << 'EOF'
stages:
  - name: "Stage 0: PDBFixer"
    command: [python, scripts/run_pdbfixer.py, --input, target.pdb, --output, outputs/fixed.pdb, --verbose]
  - name: "Stage 1: RFdiffusion"
    command: [python, scripts/run_rfdiffusion.py, --input-pdb, outputs/fixed.pdb, --contig, "[B1-100/0 100-100]", --num-designs, "20", --output-prefix, outputs/binder/design, --verbose]
  - name: "Stage 2: ProteinMPNN"
    command: [python, scripts/run_proteinmpnn.py, --pdb-path, "outputs/binder/design_*.pdb", --out-folder, outputs/binder/seqs/, --num-seq, "8", --verbose]
  - name: "Stage 3: OmegaFold"
    command: [python, scripts/run_omegafold.py, --input, outputs/binder/seqs/seqs.fa, --output-dir, outputs/binder/validation/, --verbose]
  - name: "Stage 4: Filtering"
    command: [python, scripts/run_filtering.py, --results-dir, outputs/binder/validation/, --min-plddt, "75", --top-n, "5", --verbose]
EOF

# Run the entire pipeline
python scripts/batch_runner.py --config binder_pipeline.yaml
```

## Step 3: Understand Your Results

### What to Expect at Each Stage

| Stage | Tool | Time (per design) | Output Files | Output Count |
|-------|------|-------------------|--------------|--------------|
| 0 | PDBFixer | ~5s | `fixed.pdb` | 1 |
| 1 | RFdiffusion | ~1-5 min | `design_0.pdb`, `design_1.pdb`, ... | N (your `--num-designs`) |
| 2 | ProteinMPNN | ~10s | `design_0.fa` (8 seqs each) | N × `--num-seq` |
| 3 | OmegaFold | ~5s/seq | `design_0.pdb` (predicted) | N × `--num-seq` |
| 3 | AlphaFold3 | ~30min/seq | JSON + PDB (predicted) | N × `--num-seq` |
| 4 | Filtering | ~1s | Ranked CSV + top PDBs | `--top-n` |

### Output Directory Structure

```
outputs/
├── monomer/
│   ├── design_0.pdb          # Backbone from RFdiffusion
│   ├── design_1.pdb
│   ├── seqs/
│   │   └── design_0.fa       # Sequences from ProteinMPNN (8 sequences)
│   └── validation/
│       └── design_0.pdb      # Predicted structure from OmegaFold
```

### Quality Metrics

| Metric | Excellent | Good | Acceptable | Poor |
|--------|-----------|------|------------|------|
| **pLDDT** | > 90 | 80-90 | 70-80 | < 70 |
| **pTM** | > 0.8 | 0.7-0.8 | 0.5-0.7 | < 0.5 |
| **ipTM** (binders) | > 0.8 | 0.7-0.8 | 0.6-0.7 | < 0.6 |

### Track Progress

```bash
# See what you've generated so far
python scripts/summarize_outputs.py --output-dir outputs/

# Live progress watch
python scripts/summarize_outputs.py --output-dir outputs/ --watch
```

## Next Steps

| I want to... | Read This |
|-------------|-----------|
| Try more design types | `pipeline-selection` skill |
| Understand each stage in depth | `full-pipeline` skill |
| Design with a ligand | `rfdiffusion-all-atom` skill |
| Design a peptide | `diffpepbuilder-design` skill |
| Speed up validation | `fast-screening` skill |
| Get the most robust results | `cross-validation` skill |
| Avoid wasting compute | `score-first-screening` skill |
| See all available tools | `SKILL_INDEX.md` |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "RFdiffusion not found" | Set `RFDIFFUSION_PATH` env var or install from GitHub |
| "Out of memory" | Reduce `--num-designs` or use a smaller GPU |
| "No databases" | Use `--validator omegafold` or `--validator esmfold` |
| "Slow validation" | Use ESMFold (~2s/sequence) instead of AlphaFold3 |
| "Want to iterate faster" | Use `score-first-screening` to pre-filter |
| "Tool not installed" | See `install-guide` skill for installation instructions |
| "No GPU" | Use ESMFold (CPU-only) or ColabFold (cloud GPU) |
| "PDB file issues" | Run PDBFixer first: `python scripts/run_pdbfixer.py -i input.pdb -o fixed.pdb` |

### Quick Health Check

```bash
# Check which tools are installed
python protein_design/hooks/session-health-check.py
```

## What to Do If Nothing Works

**If you can't install any tools:**

1. **Use ESMFold only** — works on CPU, no databases, pip install
   ```bash
   pip install fair-esm
   python scripts/run_esmfold.py --input seqs.fa --output-dir outputs/
   ```

2. **Use ColabDesign** — free cloud GPU, no local installation
   See `colabdesign-workflow` skill.

3. **Use Boltz-1** — MIT license, no databases, pip install
   ```bash
   pip install boltz
   python scripts/run_boltz.py --input input.yaml --out-dir outputs/boltz/
   ```

**If you have a PDB file but no tools:**

```bash
# At minimum, you can analyze the PDB file directly
python -c "
from Bio.PDB import PDBParser
p = PDBParser(QUIET=True)
s = p.get_structure('x', 'target.pdb')
print(f'Chains: {[c.id for c in s.get_chains()]}')
print(f'Residues: {len(list(s.get_residues()))}')
"
```

## One-Command Summary

```bash
# Full pipeline: preprocess → design → sequence → validate → filter
python scripts/batch_runner.py \
    --input-pdb target.pdb \
    --contig "150-150" \
    --validator omegafold \
    --output-dir outputs/my_design \
    --verbose
```

That's it. You now have a designed protein.

## Get Help

| Need | How |
|------|-----|
| Tool not found | Run `python protein_design/hooks/session-health-check.py` |
| Which pipeline to use | Read `pipeline-selection` skill |
| How to install tools | Read `install-guide` skill |
| What to do next | Read `next-steps` skill |
| Error during execution | The `error-recovery` hook will suggest fixes automatically |
| Track progress | `python scripts/summarize_outputs.py --output-dir outputs/` |
| See all skills | Read `SKILL_INDEX.md` |
