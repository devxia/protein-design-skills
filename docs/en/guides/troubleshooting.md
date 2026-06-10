---
title: Troubleshooting
source: README.md
---

# Troubleshooting

## Common issues

| Issue | Solution |
|-------|----------|
| Plugin not loading | Run `/new` after installation |
| `run_pdbfixer` not found | `conda install -c conda-forge pdbfixer openmm`, or use `conda_env` param to run in another env |
| RFdiffusion not found | Set `RFDIFFUSION_PATH` env var |
| GPU out of memory | Reduce `num_designs` or `diffuser_T` |
| AlphaFold3 MSA timeout | Default runs full MSA. Set `run_data_pipeline=false` to skip (faster, less accurate) |
| Tool not found in other env | `check_all_tools` now auto-scans common conda envs + editable installs |
| Binder validation needs receptor | Use `convert_format` with `receptor_pdb` to generate multi-chain AF3 JSON |
| Hooks not working | Verify agent hook config syntax, then restart the session |

## Cross-Conda environment execution

If your tools are installed in different conda environments, you don't need to install them all in one env:

- **`run_pdbfixer`**: Use `conda_env="BindCraft"` to run PDBFixer in the target environment
- **`run_rfdiffusion` / `run_proteinmpnn` / `run_alphafold3`**: Use `conda_env` or `wrapper_script` to specify the target environment

The plugin auto-detects tools across common conda environments and editable installs.

## Multi-chain complex validation

For binder/peptide design validation, AlphaFold3 needs both the receptor and the designed peptide in one JSON:

```python
convert_format(
    from_format="fasta",
    to_format="alphafold3_json",
    input_path="/path/to/proteinmpnn_out.fasta",
    receptor_pdb="/path/to/receptor_fixed.pdb",
    receptor_chain="A",
    job_name="binder_validation"
)
```

After AlphaFold3 finishes, analyze results without re-running:

```python
analyze_alphafold3_results(
    output_dir="/path/to/af3_output",
    job_name="binder_validation"
)
# Returns: per-chain pLDDT, ipTM, pTM, ranking scores, clash status, best structure
```
