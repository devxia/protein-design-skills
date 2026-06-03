# API Reference — Tools

This page documents all MCP tools provided by the protein design plugin.

## `get_tool_info`

Get information about all available tools, their parameters, and usage.

## `health_check`

Check the health of the protein design environment: GPU, CUDA, conda, tool installations, and disk space.

## `get_gpu_status`

Get detailed GPU status including availability, memory, and architecture recommendations.

## `submit_job`

Submit an async job for a protein design tool. Returns a task_id for polling via query_job.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tool` | enum(rfdiffusion, proteinmpnn, alphafold3, pdbfixer, filtering) | Yes | — | Tool name to execute |
| `params` | object | Yes | — | Tool-specific parameters (see get_tool_info for details) |

## `query_job`

Query the status and results of a submitted job by task_id.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_id` | string | Yes | — | Task ID returned by submit_job |

## `cancel_job`

Cancel a running or queued job by task_id.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_id` | string | Yes | — | Task ID to cancel |

## `run_pdbfixer`

Preprocess a PDB/CIF file with PDBFixer. Mandatory before RFdiffusion/ProteinMPNN. Fixes non-standard residues, removes heterogens, adds missing heavy atoms. Does NOT add hydrogens or missing loops. Supports cross-conda-environment execution via conda_env.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `input_pdb` | string | Yes | — | Input PDB/CIF file path |
| `output_pdb` | string | No | — | Output PDB file path (auto-generated if omitted) |
| `output_dir` | string | No | — | Output directory when output_pdb is not specified |
| `keep_chains` | array[string] | No | — | Chain IDs to retain (e.g., ['A', 'B']). All kept if omitted. |
| `seed` | integer | No | 42 | Random seed for missing atom reconstruction |
| `conda_env` | string | No | — | Optional conda environment name where PDBFixer is installed. Use this when PDBFixer is not in the current environment. |

## `run_rfdiffusion`

Run RFdiffusion for protein backbone generation. Supports unconditional monomers, motif scaffolding, binder design, and symmetric oligomers. Input PDB is automatically preprocessed with PDBFixer unless skip_preprocessing=true.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `output_prefix` | string | Yes | — | Output path prefix |
| `num_designs` | integer | No | 10 | Number of designs to generate |
| `input_pdb` | string | No | — | Input PDB path (required for motif/binder/partial) |
| `contig` | string | Yes | — | Contig string, e.g. '[150-150]' or '[B1-100/0 100-100]' |
| `hotspot_res` | array[string] | No | — | Hotspot residues for binder design, e.g. ['A30','A33'] |
| `symmetry` | string | No | — | Symmetry mode: c2, d2, tetrahedral, etc. |
| `diffuser_T` | integer | No | 50 | Diffusion timesteps (smaller=faster) |
| `ckpt_override_path` | string | No | — | Override default model checkpoint |
| `skip_preprocessing` | boolean | No | False | Skip automatic PDBFixer preprocessing |
| `keep_chains` | array[string] | No | — | Chains to keep during preprocessing |
| `conda_env` | string | No | — | Conda environment name for RFdiffusion (e.g. 'SE3nv'). Falls back to config or current env. |
| `wrapper_script` | string | No | — | Optional path to a shell wrapper script that sets up the environment (env vars, conda activation, etc.) before running RFdiffusion. Overrides conda_env. |

## `run_proteinmpnn`

Run ProteinMPNN for amino acid sequence design on a given backbone PDB.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pdb_path` | string | Yes | — | Input PDB file path |
| `output_folder` | string | Yes | — | Output folder path |
| `num_seq_per_target` | integer | No | 8 | Sequences per target |
| `sampling_temp` | string | No | 0.1 | Sampling temperature(s), e.g. '0.1' or '0.1 0.2 0.3' |
| `model_name` | string | No | v_48_020 | Model variant |
| `pdb_path_chains` | string | No | — | Chains to design, e.g. 'B' for binder-only |
| `fixed_positions_jsonl` | string | No | — | Path to fixed positions JSONL |
| `use_soluble_model` | boolean | No | False | Use soluble protein model |
| `seed` | integer | No | 37 | Random seed |
| `conda_env` | string | No | — | Conda environment name for ProteinMPNN. Falls back to config or current env. |
| `wrapper_script` | string | No | — | Optional path to a shell wrapper script that sets up the environment before running ProteinMPNN. Overrides conda_env. |

## `run_alphafold3`

Run AlphaFold3 for structure prediction and validation. Accepts JSON input ( ProteinMPNN FASTA output can be converted with convert_format first).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `json_path` | string | Yes | — | Input JSON file path |
| `model_dir` | string | No | — | AlphaFold3 model parameters directory |
| `db_dir` | string | No | — | Genetic databases directory |
| `output_dir` | string | Yes | — | Output directory |
| `num_seeds` | integer | No | 1 | Number of seeds |
| `num_samples` | integer | No | 5 | Samples per seed |
| `run_data_pipeline` | boolean | No | True | Run MSA search (CPU-only, slow). Default true. Set to false only for fast inference with pre-computed features or no-MSA mode. |
| `conda_env` | string | No | — | Conda environment name for AlphaFold3. Falls back to config or current env. |
| `wrapper_script` | string | No | — | Optional path to a shell wrapper script (e.g., run_af3.sh) that sets up the environment (XLA_FLAGS, model_dir, db_dir, HMMER paths) before running AlphaFold3. Overrides conda_env and auto-detected db_dir. |

## `convert_format`

Convert between protein design file formats: ProteinMPNN FASTA to AlphaFold3 JSON (with optional receptor PDB for multi-chain complexes), or validate PDB.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `from_format` | enum(fasta, pdb) | Yes | — | Source format |
| `to_format` | enum(alphafold3_json, validated_pdb) | Yes | — | Target format |
| `input_path` | string | Yes | — | Input file path |
| `output_path` | string | No | — | Output file path |
| `job_name` | string | No | — | Job name for AF3 JSON |
| `seed` | integer | No | 1 | Seed for AF3 JSON |
| `receptor_pdb` | string | No | — | Optional path to receptor PDB file. When provided, the receptor sequence is prepended to the design sequence for multi-chain AlphaFold3 input. |
| `receptor_chain` | string | No | — | Optional chain ID in receptor_pdb to extract. If omitted, uses the first available chain. |

## `analyze_alphafold3_results`

Parse and analyze AlphaFold3 prediction results from an output directory. Extracts confidence metrics (pLDDT, pTM, ipTM, per-chain pLDDT, ranking scores, clash status) without re-running the prediction.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `output_dir` | string | Yes | — | AlphaFold3 output directory to analyze |
| `job_name` | string | No | — | Optional job name used for output files. Auto-detected if omitted. |

## `run_filtering`

Filter and rank protein designs by AlphaFold3 confidence metrics (pLDDT, ipTM, pTM, clashes).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `designs` | array[object] | Yes | — | List of design result dicts with metrics |
| `criteria` | object | No | — |  |

## `check_batch_progress`

Check the progress of a batch of submitted jobs.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_ids` | array[string] | Yes | — | List of task IDs to check |

## `check_tool_status`

Check whether a specific protein design tool is installed and detectable. Returns installation status, detected path, and download instructions if missing.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tool_name` | enum(rfdiffusion, proteinmpnn, alphafold3, pdbfixer) | Yes | — | Tool name to check |

## `check_all_tools`

Check the installation status of all protein design tools at once. Returns a summary with per-tool status and overall readiness.

## `configure_tool_path`

Configure the installation path for a tool and persist it to config. Use this after installing a tool so the plugin can find it. Validates that expected files exist at the given path. Optionally sets the conda environment name.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tool_name` | enum(rfdiffusion, proteinmpnn, alphafold3) | Yes | — | Tool to configure |
| `path` | string | Yes | — | Absolute path to the tool's root directory (e.g., /home/you/RFdiffusion) |
| `conda_env` | string | No | — | Optional conda environment name (e.g., 'SE3nv' for RFdiffusion) |

## `configure_db_dir`

Configure the AlphaFold3 genetic database directory (e.g., ~/public_databases). Validates the directory contains expected database subdirectories. Persists to config file.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | — | Absolute path to the genetic databases directory (e.g., /home/you/public_databases) |

