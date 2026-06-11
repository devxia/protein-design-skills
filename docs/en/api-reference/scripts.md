# API Reference — Standalone Scripts

This page documents all standalone scripts in the `scripts/` directory. These scripts are the **primary execution method** for the protein design pipeline.

---

## Script Index

| Script | Stage | Purpose |
|--------|-------|---------|
| `run_pdbfixer.py` | 0 | PDB preprocessing and repair |
| `run_rfdiffusion.py` | 1 | Backbone generation |
| `run_proteinmpnn.py` | 2 | Sequence design |
| `run_alphafold3.py` | 3 | Structure validation (best accuracy) |
| `run_boltz.py` | 3 | Boltz-1 validation (MIT, complexes) |
| `run_chai1.py` | 3 | Chai-1 validation (Apache 2.0) |
| `run_omegafold.py` | 3 | OmegaFold validation (fast, no DB) |
| `run_esmfold.py` | 3 | ESMFold validation (fastest) |
| `run_protenix.py` | 3 | Protenix validation (training + inference) |
| `run_openfold3.py` | 3 | OpenFold3 validation (pip install) |
| `run_filtering.py` | 4 | Result filtering and ranking |
| `convert_format.py` | — | File format conversion |
| `job_manager.py` | — | Background job tracking |
| `batch_runner.py` | — | Complete pipeline orchestration |
| `summarize_outputs.py` | — | Progress summary + quality report |
| `project_dashboard.py` | — | Project-wide multi-stage dashboard |

---

## `run_pdbfixer.py`

Preprocess a PDB/CIF file with PDBFixer. Mandatory before RFdiffusion/ProteinMPNN. Fixes non-standard residues, removes heterogens, adds missing heavy atoms. Does NOT add hydrogens or missing loops.

### Usage

```bash
python scripts/run_pdbfixer.py \
    --input target.pdb \
    --output target_fixed.pdb \
    [--keep-chains A B] \
    [--seed 42] \
    [--verbose]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--input` / `-i` | string | Yes | — | Input PDB/CIF file path |
| `--output` / `-o` | string | No | — | Output PDB file path (auto-generated if omitted) |
| `--output-dir` | string | No | — | Output directory when --output is not specified |
| `--keep-chains` | string[] | No | — | Chain IDs to retain (e.g., `A B`). All kept if omitted |
| `--seed` | integer | No | 42 | Random seed for missing atom reconstruction |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `run_rfdiffusion.py`

Run RFdiffusion for protein backbone generation. Supports unconditional monomers, motif scaffolding, binder design, symmetric oligomers, partial diffusion, inpainting, secondary structure specification, fold conditioning, cyclic peptides, and potentials-guided design.

> Input PDB is automatically preprocessed with PDBFixer unless `--skip-preprocessing` is set.

### Usage

```bash
python scripts/run_rfdiffusion.py \
    --contig "150-150" \
    --num-designs 50 \
    --output-prefix outputs/design \
    [--input-pdb target.pdb] \
    [--hotspot-res A30 A33] \
    [--verbose]
```

### Basic Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--output-prefix` | string | Yes | — | Output path prefix |
| `--num-designs` / `-n` | integer | No | 10 | Number of designs to generate |
| `--input-pdb` | string | No | — | Input PDB path (required for motif/binder/partial/inpainting) |
| `--contig` | string | Yes | — | Contig string, e.g. `[150-150]` or `[B1-100/0 100-100]` |
| `--hotspot-res` | string[] | No | — | Hotspot residues for binder design, e.g. `A30 A33` |
| `--symmetry` | string | No | — | Symmetry mode: `c2`, `c3`, `c4`, `d2`, `d3`, `tetrahedral`, `octahedral`, `icosahedral` |
| `--diffuser-T` | integer | No | 50 | Diffusion timesteps (smaller=faster). Use 25 for partial diffusion |
| `--ckpt-override-path` | string | No | — | Override default model checkpoint. E.g. `models/ActiveSite_ckpt.pt` for enzyme active sites |
| `--skip-preprocessing` | flag | No | False | Skip automatic PDBFixer preprocessing |
| `--keep-chains` | string[] | No | — | Chains to keep during preprocessing |
| `--verbose` / `-v` | flag | No | False | Verbose output |

### Advanced Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--partial-T` | integer | No | — | Partial diffusion: add noise for N steps then denoise (e.g. 10) |
| `--provide-seq` | string | No | — | Keep sequence fixed during partial diffusion. Format: `[172-205]` |
| `--inpaint-seq` | string | No | — | Mask sequence identity of residues. Format: `[A163-168/A170-171]` |
| `--inpaint-str` | string | No | — | Mask 3D structure while keeping sequence. Format: `[B165-178]` |
| `--inpaint-str-helix` | string | No | — | Specify masked residues as alpha-helix. Format: `[A51-60]` |
| `--inpaint-str-strand` | string | No | — | Specify masked residues as beta-strand. Format: `[A61-70]` |
| `--inpaint-str-loop` | string | No | — | Specify masked residues as loop. Format: `[A71-80]` |
| `--scaffoldguided` | flag | No | False | Enable fold conditioning via secondary structure + block adjacency |
| `--scaffold-dir` | string | No | — | Directory with scaffold ss/adj files (required when --scaffoldguided) |
| `--cyclic` | flag | No | False | Design macrocyclic peptides |
| `--cyc-chains` | string | No | a | Chain(s) to cyclize (default: `a`) |
| `--potentials` | string[] | No | — | Guiding potentials. E.g. `type:monomer_ROG,weight:1.0` |
| `--final-step` | integer | No | — | Stop diffusion early at this step (faster, lower quality) |
| `--noise-scale-ca` | float | No | — | CA coordinate noise scale (lower=less diverse, higher quality) |
| `--noise-scale-frame` | float | No | — | Frame noise scale (lower=less diverse, higher quality) |

### Model Checkpoints (Auto-selected)

| Checkpoint | Auto-selected When |
|------------|-------------------|
| `Base_ckpt.pt` | Default (no special flags) |
| `Complex_base_ckpt.pt` | `--hotspot-res` is set |
| `Complex_Fold_base_ckpt.pt` | `--scaffoldguided` is set |
| `InpaintSeq_ckpt.pt` | `--inpaint-seq` or `--provide-seq` or `--inpaint-str` set |
| `ActiveSite_ckpt.pt` | Manual override only (very small motifs) |

---

## `run_proteinmpnn.py`

Run ProteinMPNN for amino acid sequence design on backbone PDBs. Supports direct PDB input, fixed positions, tied positions (symmetry), AA bias, PSSM bias, and scoring-only mode.

### Usage

```bash
python scripts/run_proteinmpnn.py \
    --pdb-path design.pdb \
    --out-folder outputs/seqs/ \
    --num-seq 8 \
    [--sampling-temp 0.1] \
    [--verbose]
```

### Basic Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--pdb-path` / `-p` | string | No | — | Input PDB file path (for single-PDB mode). Use either --pdb-path OR --jsonl-path |
| `--jsonl-path` | string | No | — | Path to parsed PDBs in jsonl format (for multi-chain batch mode) |
| `--out-folder` / `-o` | string | Yes | — | Output folder path |
| `--num-seq` / `-n` | integer | No | 8 | Sequences per target |
| `--sampling-temp` | string | No | 0.1 | Sampling temperature(s), e.g. `0.1` or `0.1 0.2 0.3` |
| `--model-name` | string | No | v_48_020 | Model variant: `v_48_002`, `v_48_010`, `v_48_020`, `v_48_030` |
| `--pdb-path-chains` | string | No | — | Chains to design for single PDB mode, e.g. `B` for binder-only |
| `--fixed-positions` | string | No | — | Fixed positions string, e.g. `B1 B2 B3` |
| `--use-soluble-model` | flag | No | False | Use soluble protein model |
| `--seed` | integer | No | 37 | Random seed (0=random) |
| `--verbose` / `-v` | flag | No | False | Verbose output |

### Advanced Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--tied-positions` | string | No | — | Tied (symmetric) positions string |
| `--bias-AA` | string | No | — | Global AA bias (e.g. `A:0.5,C:-1.0`) |
| `--bias-by-res` | string | No | — | Per-position AA bias |
| `--pssm` | string | No | — | PSSM bias file path |
| `--pssm-multi` | float | No | 0.0 | PSSM weight [0.0, 1.0] |
| `--omit-AAs` | string | No | X | Exclude amino acids, e.g. `AC` excludes Ala and Cys |
| `--backbone-noise` | float | No | 0.0 | Gaussian noise std dev on backbone atoms (A) |
| `--save-score` | flag | No | False | Save scores to .npz files |
| `--save-probs` | flag | No | False | Save predicted probabilities to .npz files |
| `--score-only` | flag | No | False | Score input backbone-sequence pairs without generating new sequences |
| `--path-to-fasta` | string | No | — | FASTA sequence to score (required when --score-only) |
| `--ca-only` | flag | No | False | Use CA-only models for CA-only structures |
| `--batch-size` | integer | No | 1 | Batch size (increase for larger GPUs) |
| `--path-to-model-weights` | string | No | — | Path to custom model weights folder |
| `--conditional-probs-only` | flag | No | False | Output conditional probabilities per position |
| `--unconditional-probs-only` | flag | No | False | Output unconditional probabilities (PSSM-like) |

---

## `run_alphafold3.py`

Run AlphaFold3 for structure prediction and validation. Accepts JSON input (ProteinMPNN FASTA output can be converted with `convert_format.py` first).

### Usage

```bash
python scripts/run_alphafold3.py \
    --json af3_input.json \
    --output-dir outputs/af3/ \
    [--num-seeds 1] \
    [--num-samples 5] \
    [--verbose]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--json` / `-j` | string | Yes | — | Input JSON file path |
| `--model-dir` | string | No | — | AlphaFold3 model parameters directory |
| `--db-dir` | string | No | — | Genetic databases directory |
| `--output-dir` / `-o` | string | Yes | — | Output directory |
| `--num-seeds` | integer | No | 1 | Number of seeds |
| `--num-samples` | integer | No | 5 | Samples per seed |
| `--run-data-pipeline` | flag | No | True | Run MSA search (CPU-only, slow) |
| `--no-run-data-pipeline` | flag | No | — | Skip MSA search (requires pre-computed features) |
| `--run-inference` | flag | No | True | Run structure prediction |
| `--save-embeddings` | flag | No | False | Save structure embeddings |
| `--save-distogram` | flag | No | False | Save distogram predictions |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `run_boltz.py`

Run Boltz-1 for structure prediction. MIT-licensed, supports complexes and covalent modifications.

### Usage

```bash
python scripts/run_boltz.py \
    --input sequences.fasta \
    --output-dir outputs/boltz/ \
    [--verbose]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--input` / `-i` | string | Yes | — | Input FASTA or YAML file path |
| `--output-dir` / `-o` | string | Yes | — | Output directory |
| `--model-dir` | string | No | — | Boltz-1 model directory |
| `--device` | string | No | cuda | Device: `cuda` or `cpu` |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `run_chai1.py`

Run Chai-1 for structure prediction. Apache 2.0 licensed.

### Usage

```bash
python scripts/run_chai1.py \
    --input sequences.fasta \
    --output-dir outputs/chai1/ \
    [--verbose]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--input` / `-i` | string | Yes | — | Input FASTA file path |
| `--output-dir` / `-o` | string | Yes | — | Output directory |
| `--num-trunk-recycles` | integer | No | 3 | Number of trunk recycles |
| `--num-diffn-steps` | integer | No | 200 | Number of diffusion steps |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `run_omegafold.py`

Run OmegaFold for fast structure prediction. No databases needed.

### Usage

```bash
python scripts/run_omegafold.py \
    --input sequences.fasta \
    --output-dir outputs/omegafold/ \
    [--verbose]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--input` / `-i` | string | Yes | — | Input FASTA file path |
| `--output-dir` / `-o` | string | Yes | — | Output directory |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `run_esmfold.py`

Run ESMFold for ultra-fast structure prediction. Best for screening large numbers of designs.

### Usage

```bash
python scripts/run_esmfold.py \
    --input sequences.fasta \
    --output-dir outputs/esmfold/ \
    [--verbose]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--input` / `-i` | string | Yes | — | Input FASTA file path |
| `--output-dir` / `-o` | string | Yes | — | Output directory |
| `--chunk-size` | integer | No | — | Chunk size for long sequences |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `run_protenix.py`

Run Protenix for structure prediction and validation. Protenix is an open-source reimplementation of AlphaFold3 with support for training and inference scaling.

### Usage

```bash
python scripts/run_protenix.py \
    --input input.json \
    --output-dir outputs/protenix/ \
    [--num-recycling 3] \
    [--verbose]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--input` / `-i` | string | Yes | — | Input JSON or FASTA file path |
| `--output-dir` / `-o` | string | Yes | — | Output directory |
| `--num-recycling` | integer | No | 3 | Number of recycling steps |
| `--from-fasta` | flag | No | False | Convert FASTA input to Protenix JSON format |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `run_openfold3.py`

Run OpenFold3 for structure prediction. OpenFold3 is an open-source reimplementation of AlphaFold3 that can be installed via pip.

> **Note**: OpenFold3 requires manual model weight and database setup. See the OpenFold3 repository for detailed instructions.

### Usage

```bash
python scripts/run_openfold3.py \
    --input sequences.fasta \
    --output-dir outputs/openfold3/ \
    [--model-dir /path/to/weights] \
    [--db-dir /path/to/databases] \
    [--verbose]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--input` / `-i` | string | Yes | — | Input FASTA or JSON file |
| `--output-dir` / `-o` | string | Yes | — | Output directory |
| `--model-dir` | string | No | — | Path to OpenFold3 model weights directory |
| `--db-dir` | string | No | — | Path to genetic databases directory |
| `--num-recycling` | integer | No | 3 | Number of recycling steps |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `run_filtering.py`

Filter and rank protein designs by confidence metrics (pLDDT, ipTM, pTM, clashes).

### Usage

```bash
python scripts/run_filtering.py \
    --results-dir outputs/af3/ \
    --min-plddt 75 \
    --top-n 10 \
    [--verbose]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--results-dir` / `-d` | string | Yes | — | Directory containing design results |
| `--min-plddt` | float | No | 70 | Minimum pLDDT threshold |
| `--min-iptm` | float | No | 0.6 | Minimum ipTM threshold |
| `--min-ptm` | float | No | 0.5 | Minimum pTM threshold |
| `--top-n` | integer | No | — | Keep top N designs after filtering |
| `--allow-clashes` | flag | No | False | Allow designs with atomic clashes |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `convert_format.py`

Convert between protein design file formats.

### Usage

```bash
python scripts/convert_format.py \
    --from fasta --to alphafold3_json \
    --input seqs.fa \
    --output af3.json \
    [--receptor-pdb receptor.pdb] \
    [--receptor-chain A]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--from` | enum | Yes | — | Source format: `fasta`, `pdb` |
| `--to` | enum | Yes | — | Target format: `alphafold3_json`, `validated_pdb` |
| `--input` / `-i` | string | Yes | — | Input file path |
| `--output` / `-o` | string | No | — | Output file path |
| `--job-name` | string | No | — | Job name for AF3 JSON |
| `--seed` | integer | No | 1 | Seed for AF3 JSON |
| `--receptor-pdb` | string | No | — | Optional receptor PDB for multi-chain AF3 input |
| `--receptor-chain` | string | No | — | Chain ID in receptor PDB to extract |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `job_manager.py`

Lightweight background job manager for tracking long-running design tasks.

### Usage

```bash
# Submit a background job
python scripts/job_manager.py submit --name rfdiff -- \
    python scripts/run_rfdiffusion.py --contig "150-150" --num-designs 50

# Check status
python scripts/job_manager.py status <job_id>

# Tail log
python scripts/job_manager.py tail <job_id> --lines 50

# Wait for completion
python scripts/job_manager.py wait <job_id> --timeout 3600

# List all jobs
python scripts/job_manager.py list

# Cancel a job
python scripts/job_manager.py cancel <job_id>
```

### Commands

| Command | Description |
|---------|-------------|
| `submit` | Submit a new background job |
| `status` | Check job status |
| `list` | List all jobs |
| `tail` | Tail job log file |
| `wait` | Wait for job completion |
| `cancel` | Cancel a running job |

### Submit Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | No | — | Job name |
| `--timeout` | integer | No | 3600 | Timeout in seconds |
| `--verbose` | flag | No | False | Verbose output |

---

## `batch_runner.py`

Run the complete protein design pipeline with a single command.

### Usage

```bash
python scripts/batch_runner.py \
    --input-pdb target.pdb \
    --contig "[B1-100/0 100-100]" \
    --validator omegafold \
    --num-designs 50 \
    --verbose
```

Or from config file:

```bash
python scripts/batch_runner.py --config pipeline.yaml
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--config` | string | No | — | Path to pipeline config YAML file |
| `--input-pdb` | string | No | — | Input PDB file path |
| `--contig` | string | No | — | RFdiffusion contig string |
| `--num-designs` | integer | No | 10 | Number of backbones to generate |
| `--num-seq` | integer | No | 8 | Sequences per backbone |
| `--validator` | string | No | alphafold3 | Validation tool: `alphafold3`, `boltz`, `chai1`, `omegafold`, `esmfold` |
| `--min-plddt` | float | No | 70 | Minimum pLDDT for filtering |
| `--output-dir` | string | No | — | Output directory |
| `--verbose` / `-v` | flag | No | False | Verbose output |

---

## `summarize_outputs.py`

Scan an output directory and print a summary of pipeline artifacts, progress bars, and validation quality metrics. Useful for periodic progress checks.

### Usage

```bash
python scripts/summarize_outputs.py \
    --output-dir outputs/ \
    [--expected-backbones 50] \
    [--expected-sequences 200] \
    [--expected-validations 50] \
    [--watch] \
    [--interval 30] \
    [--json]
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--output-dir` / `-d` | string | Yes | — | Directory to scan |
| `--expected-backbones` | integer | No | 0 | Expected PDB count for progress bar |
| `--expected-sequences` | integer | No | 0 | Expected FASTA count for progress bar |
| `--expected-validations` | integer | No | 0 | Expected validation count for progress bar |
| `--watch` / `-w` | flag | No | False | Auto-refresh until interrupted |
| `--interval` / `-i` | integer | No | 30 | Refresh interval in seconds |
| `--json` / `-j` | flag | No | False | Emit raw JSON instead of formatted text |

### Output Summary

- **Artifact counts**: PDB backbones, FASTA sequences, confidence JSON files, mmCIF structures
- **Progress bars**: Percentage complete against expected counts
- **Quality distribution**: Designs bucketed by pLDDT (Excellent ≥90, Good 80–90, Acceptable 70–80, Poor <70)
- **Top designs**: Ranked table by pLDDT with ipTM and pTM

---

## `project_dashboard.py`

Project-wide pipeline dashboard. Scans the output directory for all pipeline stages (preprocessing, backbone, sequence, validation, filtering) and prints a consolidated summary with artifact counts, progress bars, quality metrics, and next-step recommendations.

### Usage

```bash
python scripts/project_dashboard.py --output-dir outputs/

# With expected counts for progress bars
python scripts/project_dashboard.py --output-dir outputs/ \
    --expected-backbones 50 \
    --expected-sequences 400 \
    --expected-validations 50

# Live watch mode
python scripts/project_dashboard.py --output-dir outputs/ --watch
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--output-dir` / `-d` | string | No | `outputs` | Root output directory to scan |
| `--expected-backbones` | integer | No | 0 | Expected backbone count for progress bar |
| `--expected-sequences` | integer | No | 0 | Expected sequence count for progress bar |
| `--expected-validations` | integer | No | 0 | Expected validation count for progress bar |
| `--watch` / `-w` | flag | No | False | Refresh every 30 seconds |
| `--json` | flag | No | False | Output JSON instead of text |

### Discovered Stages

The dashboard looks for subdirectories matching common stage names:
- **Preprocessing**: `preprocessing/`, `pdbfixer/`, `fixed/`, `preprocess/`
- **Backbone**: `backbone/`, `rfdiffusion/`, `backbones/`, `designs/`
- **Sequence**: `sequence/`, `proteinmpnn/`, `seqs/`, `sequences/`
- **Validation**: `validation/`, `alphafold3/`, `af3/`, `boltz/`, `chai1/`, `validated/`
- **Filtering**: `filtering/`, `filtered/`, `ranking/`

### Output

The dashboard reports:
- Overall artifact counts
- Per-stage progress bars against expected targets
- Mean / best / worst pLDDT and ipTM
- Quality distribution (Excellent/Good/Acceptable/Poor)
- Passing design count from `filtered_results.json`
- Next-step recommendation based on detected stages

---

## Exit Codes

All scripts use the following exit code convention:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Input file not found |
| 2 | Tool not installed / not found |
| 3 | Execution error |
| 4 | Invalid arguments |

---

## Configuration Priority

Scripts read configuration from (in order of priority):

1. Command-line arguments (highest priority)
2. Environment variables (`RFDIFFUSION_PATH`, `PROTEINMPNN_PATH`, etc.)
3. `~/.protein-design/config.yaml`
4. `~/.kimi-protein-design/config.yaml` (legacy)
5. Auto-detection (common paths, conda envs)

## History Logging

All scripts write execution records to `~/.protein-design/history.jsonl` for future ETA estimation and progress tracking.
