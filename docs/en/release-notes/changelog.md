# Changelog

This page documents the changes in each release of the Kimi Protein Design plugin.

## 2025-06-01

### Features

- Initial commit of kimi-protein-design plugin with 5-stage protein design pipeline
- Add conda environment support for RFdiffusion, ProteinMPNN, and AlphaFold3
- Add file-based progress tracking with historical ETA estimation
- Add cross-conda-environment support for PDBFixer via `conda_env` parameter
- Add `receptor_pdb` support to `convert_format` for multi-chain AF3 JSON generation
- Add `analyze_alphafold3_results` tool for parsing AlphaFold3 output metrics without re-running
- Add editable-install detection in `check_all_tools` for pip-installed packages

### Bug fixes

- Address all plugin issues from first server run log analysis
- Fix missing `import time` in `alphafold.py` causing `submit_job` to crash
- Fix `run_filtering` ignoring top-level metric fields (plddt, iptm, ptm, has_clash)
- Fix RFdiffusion contig double-bracketing when user provides brackets in contig string

### Docs

- Reorder README sections and replace placeholder owner with devxia
- Add prominent "already installed?" tip before Prerequisites Installation steps
- Update README for wrapper_script, schema, and MSA behavior changes
