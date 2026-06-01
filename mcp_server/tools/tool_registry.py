"""Tool registry for the protein design MCP server.

Defines all available tools with their JSON Schema parameters and
 dispatches tool calls to the appropriate implementation.
"""

import logging
from typing import Any, Callable

from mcp_server.tools.job_manager import JOB_MANAGER, JobManager
from mcp_server.tools.system_info import health_check, get_gpu_status
from mcp_server.tools.pdbfixer_tool import run_pdbfixer
from mcp_server.tools.tool_installer import (
    check_tool_status,
    check_all_tools,
    configure_tool_path,
    configure_db_dir,
    get_missing_tool_prompt,
)

logger = logging.getLogger(__name__)

# Tool schema definitions
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_tool_info",
        "description": "Get information about all available tools, their parameters, and usage.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "health_check",
        "description": "Check the health of the protein design environment: GPU, CUDA, conda, tool installations, and disk space.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "submit_job",
        "description": "Submit an async job for a protein design tool. Returns a task_id for polling via query_job.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool": {
                    "type": "string",
                    "enum": ["rfdiffusion", "proteinmpnn", "alphafold3", "pdbfixer", "filtering"],
                    "description": "Tool name to execute",
                },
                "params": {
                    "type": "object",
                    "description": "Tool-specific parameters (see get_tool_info for details)",
                },
            },
            "required": ["tool", "params"],
        },
    },
    {
        "name": "query_job",
        "description": "Query the status and results of a submitted job by task_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID returned by submit_job",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "cancel_job",
        "description": "Cancel a running or queued job by task_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to cancel",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "run_pdbfixer",
        "description": "Preprocess a PDB/CIF file with PDBFixer. Mandatory before RFdiffusion/ProteinMPNN. Fixes non-standard residues, removes heterogens, adds missing heavy atoms. Does NOT add hydrogens or missing loops.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_pdb": {"type": "string", "description": "Input PDB/CIF file path"},
                "output_pdb": {"type": "string", "description": "Output PDB file path (auto-generated if omitted)"},
                "output_dir": {"type": "string", "description": "Output directory when output_pdb is not specified"},
                "keep_chains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Chain IDs to retain (e.g., ['A', 'B']). All kept if omitted.",
                },
                "seed": {"type": "integer", "default": 42, "description": "Random seed for missing atom reconstruction"},
            },
            "required": ["input_pdb"],
        },
    },
    {
        "name": "run_rfdiffusion",
        "description": "Run RFdiffusion for protein backbone generation. Supports unconditional monomers, motif scaffolding, binder design, and symmetric oligomers. Input PDB is automatically preprocessed with PDBFixer unless skip_preprocessing=true.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_prefix": {"type": "string", "description": "Output path prefix"},
                "num_designs": {"type": "integer", "default": 10, "description": "Number of designs to generate"},
                "input_pdb": {"type": "string", "description": "Input PDB path (required for motif/binder/partial)"},
                "contig": {"type": "string", "description": "Contig string, e.g. '[150-150]' or '[B1-100/0 100-100]'"},
                "hotspot_res": {"type": "array", "items": {"type": "string"}, "description": "Hotspot residues for binder design, e.g. ['A30','A33']"},
                "symmetry": {"type": "string", "description": "Symmetry mode: c2, d2, tetrahedral, etc."},
                "diffuser_T": {"type": "integer", "default": 50, "description": "Diffusion timesteps (smaller=faster)"},
                "ckpt_override_path": {"type": "string", "description": "Override default model checkpoint"},
                "skip_preprocessing": {"type": "boolean", "default": False, "description": "Skip automatic PDBFixer preprocessing"},
                "keep_chains": {"type": "array", "items": {"type": "string"}, "description": "Chains to keep during preprocessing"},
                "conda_env": {"type": "string", "description": "Conda environment name for RFdiffusion (e.g. 'SE3nv'). Falls back to config or current env."},
                "wrapper_script": {"type": "string", "description": "Optional path to a shell wrapper script that sets up the environment (env vars, conda activation, etc.) before running RFdiffusion. Overrides conda_env."},
            },
            "required": ["output_prefix", "contig"],
        },
    },
    {
        "name": "run_proteinmpnn",
        "description": "Run ProteinMPNN for amino acid sequence design on a given backbone PDB.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdb_path": {"type": "string", "description": "Input PDB file path"},
                "output_folder": {"type": "string", "description": "Output folder path"},
                "num_seq_per_target": {"type": "integer", "default": 8, "description": "Sequences per target"},
                "sampling_temp": {"type": "string", "default": "0.1", "description": "Sampling temperature(s), e.g. '0.1' or '0.1 0.2 0.3'"},
                "model_name": {"type": "string", "default": "v_48_020", "description": "Model variant"},
                "pdb_path_chains": {"type": "string", "description": "Chains to design, e.g. 'B' for binder-only"},
                "fixed_positions_jsonl": {"type": "string", "description": "Path to fixed positions JSONL"},
                "use_soluble_model": {"type": "boolean", "default": False, "description": "Use soluble protein model"},
                "seed": {"type": "integer", "default": 37, "description": "Random seed"},
                "conda_env": {"type": "string", "description": "Conda environment name for ProteinMPNN. Falls back to config or current env."},
                "wrapper_script": {"type": "string", "description": "Optional path to a shell wrapper script that sets up the environment before running ProteinMPNN. Overrides conda_env."},
            },
            "required": ["pdb_path", "output_folder"],
        },
    },
    {
        "name": "run_alphafold3",
        "description": "Run AlphaFold3 for structure prediction and validation. Accepts JSON input ( ProteinMPNN FASTA output can be converted with convert_format first).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "json_path": {"type": "string", "description": "Input JSON file path"},
                "model_dir": {"type": "string", "description": "AlphaFold3 model parameters directory"},
                "db_dir": {"type": "string", "description": "Genetic databases directory"},
                "output_dir": {"type": "string", "description": "Output directory"},
                "num_seeds": {"type": "integer", "default": 1, "description": "Number of seeds"},
                "num_samples": {"type": "integer", "default": 5, "description": "Samples per seed"},
                "run_data_pipeline": {"type": "boolean", "default": True, "description": "Run MSA search (CPU-only, slow). Default true. Set to false only for fast inference with pre-computed features or no-MSA mode."},
                "conda_env": {"type": "string", "description": "Conda environment name for AlphaFold3. Falls back to config or current env."},
                "wrapper_script": {"type": "string", "description": "Optional path to a shell wrapper script (e.g., run_af3.sh) that sets up the environment (XLA_FLAGS, model_dir, db_dir, HMMER paths) before running AlphaFold3. Overrides conda_env and auto-detected db_dir."},
            },
            "required": ["json_path", "output_dir"],
        },
    },
    {
        "name": "convert_format",
        "description": "Convert between protein design file formats: ProteinMPNN FASTA to AlphaFold3 JSON, or validate PDB.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_format": {"type": "string", "enum": ["fasta", "pdb"], "description": "Source format"},
                "to_format": {"type": "string", "enum": ["alphafold3_json", "validated_pdb"], "description": "Target format"},
                "input_path": {"type": "string", "description": "Input file path"},
                "output_path": {"type": "string", "description": "Output file path"},
                "job_name": {"type": "string", "description": "Job name for AF3 JSON"},
                "seed": {"type": "integer", "default": 1, "description": "Seed for AF3 JSON"},
            },
            "required": ["from_format", "to_format", "input_path"],
        },
    },
    {
        "name": "run_filtering",
        "description": "Filter and rank protein designs by AlphaFold3 confidence metrics (pLDDT, ipTM, pTM, clashes).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "designs": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of design result dicts with metrics",
                },
                "criteria": {
                    "type": "object",
                    "properties": {
                        "min_plddt": {"type": "number", "default": 70},
                        "min_iptm": {"type": "number", "default": 0.6},
                        "min_ptm": {"type": "number", "default": 0.5},
                        "allow_clashes": {"type": "boolean", "default": False},
                    },
                },
            },
            "required": ["designs"],
        },
    },
    {
        "name": "check_batch_progress",
        "description": "Check the progress of a batch of submitted jobs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of task IDs to check",
                },
            },
            "required": ["task_ids"],
        },
    },
    {
        "name": "check_tool_status",
        "description": "Check whether a specific protein design tool is installed and detectable. Returns installation status, detected path, and download instructions if missing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "enum": ["rfdiffusion", "proteinmpnn", "alphafold3", "pdbfixer"],
                    "description": "Tool name to check",
                },
            },
            "required": ["tool_name"],
        },
    },
    {
        "name": "check_all_tools",
        "description": "Check the installation status of all protein design tools at once. Returns a summary with per-tool status and overall readiness.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "configure_tool_path",
        "description": "Configure the installation path for a tool and persist it to config. Use this after installing a tool so the plugin can find it. Validates that expected files exist at the given path. Optionally sets the conda environment name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "enum": ["rfdiffusion", "proteinmpnn", "alphafold3"],
                    "description": "Tool to configure",
                },
                "path": {
                    "type": "string",
                    "description": "Absolute path to the tool's root directory (e.g., /home/you/RFdiffusion)",
                },
                "conda_env": {
                    "type": "string",
                    "description": "Optional conda environment name (e.g., 'SE3nv' for RFdiffusion)",
                },
            },
            "required": ["tool_name", "path"],
        },
    },
    {
        "name": "configure_db_dir",
        "description": "Configure the AlphaFold3 genetic database directory (e.g., ~/public_databases). Validates the directory contains expected database subdirectories. Persists to config file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the genetic databases directory (e.g., /home/you/public_databases)",
                },
            },
            "required": ["path"],
        },
    },
]

# Map tool names to their execution functions
# Note: rfdiffusion, proteinmpnn, alphafold3, filtering are imported later
# to avoid circular dependencies during module loading.
_TOOL_EXECUTORS: dict[str, Callable[[dict[str, Any], callable], dict[str, Any]]] = {
    "run_pdbfixer": run_pdbfixer,
}


def _ensure_tool_executors() -> None:
    """Lazy-load tool executors to avoid circular imports."""
    global _TOOL_EXECUTORS
    if "run_rfdiffusion" in _TOOL_EXECUTORS:
        return

    try:
        from mcp_server.tools.rfdiffusion import run_rfdiffusion
        _TOOL_EXECUTORS["run_rfdiffusion"] = run_rfdiffusion
    except ImportError as exc:
        logger.warning("RFdiffusion tool not available: %s", exc)

    try:
        from mcp_server.tools.proteinmpnn import run_proteinmpnn
        _TOOL_EXECUTORS["run_proteinmpnn"] = run_proteinmpnn
    except ImportError as exc:
        logger.warning("ProteinMPNN tool not available: %s", exc)

    try:
        from mcp_server.tools.alphafold import run_alphafold3
        _TOOL_EXECUTORS["run_alphafold3"] = run_alphafold3
    except ImportError as exc:
        logger.warning("AlphaFold3 tool not available: %s", exc)

    try:
        from mcp_server.tools.filtering import run_filtering
        _TOOL_EXECUTORS["run_filtering"] = run_filtering
    except ImportError as exc:
        logger.warning("Filtering tool not available: %s", exc)


def get_tool_info() -> dict[str, Any]:
    """Return information about all available tools.

    Returns:
        Dict with list of tool schemas.
    """
    _ensure_tool_executors()
    return {"tools": TOOL_SCHEMAS, "count": len(TOOL_SCHEMAS)}


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name with given arguments.

    Args:
        name: Tool name.
        arguments: Tool arguments dict.

    Returns:
        Tool result dict.
    """
    logger.info("Executing tool: %s with args: %s", name, arguments)

    if name == "get_tool_info":
        return get_tool_info()

    if name == "health_check":
        return health_check()

    if name == "get_gpu_status":
        return get_gpu_status()

    if name == "submit_job":
        tool = arguments.get("tool")
        params = arguments.get("params", {})
        _ensure_tool_executors()
        executor = _TOOL_EXECUTORS.get(f"run_{tool}")
        if not executor:
            return {"error": f"Unknown tool for submit_job: {tool}"}
        return JOB_MANAGER.submit_job(tool, params, executor)

    if name == "query_job":
        return JOB_MANAGER.query_job(arguments["task_id"])

    if name == "cancel_job":
        return JOB_MANAGER.cancel_job(arguments["task_id"])

    if name == "check_batch_progress":
        results = []
        for task_id in arguments.get("task_ids", []):
            results.append(JOB_MANAGER.query_job(task_id))
        return {"batch_results": results, "total": len(results)}

    if name == "check_tool_status":
        return check_tool_status(arguments["tool_name"])

    if name == "check_all_tools":
        return check_all_tools()

    if name == "configure_tool_path":
        return configure_tool_path(
            arguments["tool_name"],
            arguments["path"],
            conda_env=arguments.get("conda_env"),
        )

    if name == "configure_db_dir":
        return configure_db_dir(arguments["path"])

    if name == "convert_format":
        from mcp_server.tools.format_converter import convert_format
        return convert_format(arguments)

    # Direct tool execution (non-async)
    _ensure_tool_executors()
    executor = _TOOL_EXECUTORS.get(name)
    if executor:
        return executor(arguments, lambda p: None)

    return {"error": f"Unknown tool: {name}"}
