---
title: Troubleshooting
source: README.md
---

# Troubleshooting

## Common issues

| Issue | Solution |
|-------|----------|
| Plugin not loading | Run `/new` after installation |
| `run_pdbfixer` not found | `conda install -c conda-forge pdbfixer openmm`, then re-run the script |
| RFdiffusion not found | Set `RFDIFFUSION_PATH` or configure `rfdiffusion_path` |
| GPU out of memory | Reduce `num_designs` or `diffuser_T` |
| AlphaFold3 MSA timeout | Re-run with `--no-msa` for faster, less accurate validation |
| Tool not found in another conda env | Runners automatically probe common conda envs; configure `<tool>_path` or `<tool>_wrapper_script` if discovery cannot find it |
| Binder validation needs receptor | Create an AlphaFold3 JSON input containing every required chain, then run `scripts/run_alphafold3.py --json input.json --output-dir outputs/af3/` |
| Hooks not working | Verify agent hook config syntax, then restart the session |

## Cross-conda environment execution

Tools may live in separate conda environments; runners automatically probe common environments and use `conda run` when a supported install is found. If a tool needs custom activation, set its configured path or `<tool>_wrapper_script` in `~/.protein-design/config.yaml`. Do not pass a `conda_env` CLI parameter: standalone runners do not expose one.

## Multi-chain complex validation

For binder or peptide validation, create an AlphaFold3 JSON input containing the receptor and designed peptide chains. Then run:

```bash
python scripts/run_alphafold3.py --json binder_input.json --output-dir outputs/af3/
```

Inspect the generated confidence JSON files with the filtering stage:

```bash
python scripts/run_filtering.py --results-dir outputs/af3/ --min-plddt 75
```
