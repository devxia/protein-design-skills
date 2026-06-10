---
name: troubleshooting
description: Comprehensive troubleshooting guide for protein design pipeline issues
---

# Troubleshooting Guide

## When to Trigger

- User says "error", "failed", "not working", "crashed", "timeout"
- User reports unexpected results (low pLDDT, no designs passing filter)
- User asks for help with a specific error message
- Tool returns non-zero exit code or missing output

## Quick Diagnostic Flow

```
Error occurred
    ↓
Identify which stage failed (0-4)
    ↓
Check error message for keywords
    ↓
Apply corresponding solution below
    ↓
If still failing → adjust parameters → retry
```

---

## Stage 0: PDBFixer Errors

### Error: "PDBFixer not found"
**Symptom**: `ImportError: No module named pdbfixer`
**Solutions**:
1. Install: `conda install -c conda-forge pdbfixer openmm`
2. Or use `conda_env` param to run in another env: `"conda_env": "myenv"`
3. Verify: `python -c "from pdbfixer import PDBFixer; print('OK')"`

### Error: "Non-standard residues"
**Symptom**: `Unknown residue MSE in chain A`
**Solution**: PDBFixer auto-converts MSE→MET, MLY→LYS, etc. This is normal.
**If conversion fails**: Manually edit PDB to use standard 3-letter codes.

### Error: "Missing atoms"
**Symptom**: `WARNING: missing_atoms` in log
**Solution**: PDBFixer auto-adds missing heavy atoms. Check output has all N/CA/C/O atoms.
**If still missing**: Input structure may be too incomplete. Try a different PDB template.

### Error: "No atoms in structure"
**Symptom**: Empty output or "0 atoms" error
**Solution**: Input file may be corrupted or have formatting issues. Try re-downloading from RCSB.

---

## Stage 1: RFdiffusion Errors

### Error: "RFdiffusion not found"
**Symptom**: `FileNotFoundError: RFdiffusion run_inference.py not found`
**Solutions**:
1. Set env var: `export RFDIFFUSION_PATH=/path/to/RFdiffusion`
2. Or configure: `configure_tool_path(tool_name="rfdiffusion", path="/path/to/RFdiffusion")`
3. Verify: `ls $RFDIFFUSION_PATH/scripts/run_inference.py`

### Error: "GPU out of memory"
**Symptom**: `CUDA out of memory` or process killed
**Solutions**:
1. Reduce `num_designs`: 50 → 20 → 10
2. Reduce `diffuser_T`: 50 → 25
3. Close other GPU processes: `nvidia-smi` to check
4. Use smaller contig length: `[200-200]` → `[150-150]`

### Error: "Contig mismatch"
**Symptom**: `Contig does not match input PDB` or `residue X not found`
**Solutions**:
1. Verify residue numbering in input PDB matches contig exactly
2. Use `grep "ATOM" input.pdb | head -20` to check numbering
3. If PDB has insertion codes (e.g., 100A), RFdiffusion may not handle them
4. Try renumbering with PDBFixer or manual editing

### Error: "No output PDBs"
**Symptom**: `0 structures` in result, empty output directory
**Solutions**:
1. Check `rfdiffusion_stderr.log` for errors
2. Verify GPU is available: `nvidia-smi`
3. Try with `diffuser_T=25` and `num_designs=1` as minimal test
4. Check contig syntax: must have brackets `[...]`

### Error: "Hotspot residues not found"
**Symptom**: `Hotspot residue A99 not in input PDB`
**Solution**: Hotspot must match chain ID + residue number exactly. Use `grep "A  99" input.pdb` to verify.

---

## Stage 2: ProteinMPNN Errors

### Error: "ProteinMPNN not found"
**Symptom**: `FileNotFoundError: protein_mpnn_run.py not found`
**Solutions**:
1. Set env var: `export PROTEINMPNN_PATH=/path/to/ProteinMPNN`
2. Or configure: `configure_tool_path(tool_name="proteinmpnn", path="/path/to/ProteinMPNN")`

### Error: "Chain ID mismatch"
**Symptom**: `Chain B not found in input PDB`
**Solutions**:
1. Check chain IDs in PDB: `grep "^ATOM" design.pdb | awk '{print $5}' | sort -u`
2. Verify `pdb_path_chains` matches actual chain IDs
3. If only one chain, omit `pdb_path_chains` entirely

### Error: "Fixed positions out of range"
**Symptom**: `Position 200 exceeds chain length 150`
**Solution**: Fixed positions use 1-based indexing (first residue = 1). Check against actual sequence length.

### Error: "JSONL file not found"
**Symptom**: `jsonl_path file does not exist`
**Solutions**:
1. Run `parse_multiple_chains.py` first to generate JSONL
2. Verify path is absolute or relative to correct directory
3. Check file has `.jsonl` extension

---

## Stage 3: AlphaFold3 Errors

### Error: "AlphaFold3 not found"
**Symptom**: `FileNotFoundError: run_alphafold.py not found`
**Solutions**:
1. Set env var: `export ALPHAFOLD_PATH=/path/to/alphafold3`
2. Or configure: `configure_tool_path(tool_name="alphafold3", path="/path/to/alphafold3")`

### Error: "MSA timeout"
**Symptom**: Process hangs for hours at "Running MSA"
**Solutions**:
1. Skip MSA: `"run_data_pipeline": false` (faster, less accurate)
2. Check databases are configured: `configure_db_dir(path="~/public_databases")`
3. Verify `~/public_databases` exists and contains bfd/, uniref90/, etc.
4. Check disk space: need ~100GB free for MSA temp files

### Error: "Database not found"
**Symptom**: `Database directory not found` or `bfd/ does not exist`
**Solutions**:
1. Download databases (~2.6TB): follow AlphaFold3 docs
2. Configure path: `configure_db_dir(path="/path/to/public_databases")`
3. Common locations: `~/public_databases`, `~/databases`, `/opt/databases`

### Error: "JSON format error"
**Symptom**: `Invalid JSON input` or schema validation error
**Solutions**:
1. Regenerate JSON with `convert_format`
2. Check JSON has required fields: `name`, `modelSeeds`, `sequences`
3. Verify sequence contains only standard amino acids (20 types)
4. Check `version` is 4 and `dialect` is "alphafold3"

### Error: "XLA/GPU error"
**Symptom**: `XLA compilation failed` or `CUDA_ERROR`
**Solutions**:
1. Set XLA flags: `export XLA_PYTHON_CLIENT_PREALLOCATE=false`
2. For older GPUs (V100): `export XLA_FLAGS="--xla_gpu_cuda_data_dir=/usr/local/cuda"`
3. Verify CUDA version matches JAX requirements
4. Try with `num_seeds=1`, `num_samples=1` as minimal test

### Error: "Out of memory during inference"
**Symptom**: AlphaFold3 killed mid-prediction
**Solutions**:
1. Reduce `num_samples`: 5 → 3 → 1
2. Reduce `num_seeds`: 1
3. Shorter sequences (<500 aa) need less memory
4. Close other GPU processes

---

## Stage 4: Filtering Errors

### Error: "All designs failed filter"
**Symptom**: 0 designs pass criteria
**Solutions**:
1. Relax criteria: `min_plddt=70` instead of 80
2. Check metrics: are they close to threshold? Small adjustment may help
3. For binders: try `min_iptm=0.6` instead of 0.8
4. Allow clashes temporarily: `"allow_clashes": true`
5. Go back to Stage 1/2: generate more designs with different parameters

### Error: "Missing metrics in designs"
**Symptom**: `KeyError: 'mean_plddt'`
**Solution**: Ensure design dicts have the expected keys. Use `analyze_alphafold3_results` to get properly formatted metrics.

---

## General Errors

### Error: "Conda environment not found"
**Symptom**: `conda run -n env_name` fails
**Solutions**:
1. Verify env exists: `conda env list`
2. Create env if missing: `conda create -n env_name python=3.9`
3. Use `wrapper_script` instead for complex setups

### Error: "Wrapper script not found"
**Symptom**: `FileNotFoundError: wrapper script`
**Solution**: Use absolute path to wrapper script. Verify file exists: `ls /path/to/wrapper.sh`

### Error: "Permission denied"
**Symptom**: Cannot write to output directory
**Solutions**:
1. Check permissions: `ls -la /path/to/output`
2. Use writable directory: `/tmp/protein-design` or `~/protein-design`
3. Set output dir explicitly in params

### Error: "Job timed out"
**Symptom**: `subprocess.TimeoutExpired`
**Solutions**:
1. Default timeout is 3600s (1 hour). Increase if needed via CONFIG
2. For AlphaFold3 with MSA: expect 30-90 min for 200-500 aa
3. Skip MSA for faster runs: `run_data_pipeline=false`
4. Use ESMFold for quick screening instead

---

## Performance Optimization

### Slow RFdiffusion
- Reduce `diffuser_T`: 50 → 25 (2x faster, slightly lower quality)
- Reduce `num_designs`
- Use GPU with more memory to avoid paging

### Slow ProteinMPNN
- Increase `batch_size` if GPU memory allows
- Reduce `num_seq_per_target`
- Use JSONL batch mode for multiple PDBs

### Slow AlphaFold3
- Skip MSA: `run_data_pipeline=false` (10x faster)
- Reduce `num_samples`: 5 → 3 → 1
- Pre-compute MSA once, reuse for multiple predictions
- Use ESMFold for initial screening

### Batch Processing Tips
- Submit all jobs first, then poll batch with `check_batch_progress`
- For >10 designs, use scheduling instead of blocking poll
- ESMFold screening → AlphaFold3 validation top 20 saves hours

---

## Getting Help

If none of the above solutions work:

1. Check the tool's stderr log: `<output_dir>/<tool>_stderr.log`
2. Run `health_check` to verify environment
3. Run `check_all_tools` to verify installations
4. Try with minimal parameters to isolate the issue
5. Check the tool's GitHub issues for similar problems
