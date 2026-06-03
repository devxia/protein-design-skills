"""Interactive tool installation helper and configuration manager.

When a tool is not found, instead of crashing, the system returns a
structured message with:
  - What is missing
  - Where to download it
  - How to configure the path

Users can then call configure_tool_path() to set paths interactively,
which are persisted to ~/.kimi-protein-design/config.yaml.
"""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from mcp_server.utils.config import CONFIG

logger = logging.getLogger(__name__)

# Installation metadata for each tool
TOOL_METADATA: dict[str, dict[str, Any]] = {
    "rfdiffusion": {
        "display_name": "RFdiffusion",
        "description": "Protein backbone generation via diffusion models",
        "download_url": "https://github.com/RosettaCommons/RFdiffusion",
        "install_guide": """
1. git clone https://github.com/RosettaCommons/RFdiffusion.git
2. cd RFdiffusion
3. conda env create -f env/SE3nv.yml
4. conda activate SE3nv
5. pip install -e .
6. Download model weights from the release page
""".strip(),
        "expected_files": ["scripts/run_inference.py"],
        "env_var": "RFDIFFUSION_PATH",
        "config_key": "rfdiffusion_path",
        "conda_env_config_key": "rfdiffusion_conda_env",
        "conda_env_example": "SE3nv",
    },
    "proteinmpnn": {
        "display_name": "ProteinMPNN",
        "description": "Amino acid sequence design on fixed backbones",
        "download_url": "https://github.com/dauparas/ProteinMPNN",
        "install_guide": """
1. git clone https://github.com/dauparas/ProteinMPNN.git
2. No pip install needed — run directly via python protein_mpnn_run.py
""".strip(),
        "expected_files": ["protein_mpnn_run.py"],
        "env_var": "PROTEINMPNN_PATH",
        "config_key": "proteinmpnn_path",
        "conda_env_config_key": "proteinmpnn_conda_env",
    },
    "alphafold3": {
        "display_name": "AlphaFold3",
        "description": "Structure prediction and confidence scoring",
        "download_url": "https://github.com/google-deepmind/alphafold3",
        "install_guide": """
Option A — Docker (Recommended):
  1. git clone https://github.com/google-deepmind/alphafold3.git
  2. cd alphafold3
  3. docker build -t alphafold3 -f docker/Dockerfile .
  4. Download models & databases per official docs

Option B — Local:
  1. git clone https://github.com/google-deepmind/alphafold3.git
  2. pip install -r requirements.txt
  3. Download model parameters to ~/models
  4. Download genetic databases to ~/public_databases
""".strip(),
        "expected_files": ["run_alphafold.py"],
        "env_var": "ALPHAFOLD_PATH",
        "config_key": "alphafold_path",
        "db_dir_config_key": "db_dir",
        "db_dir_env_var": "PROTEIN_DESIGN_DB_DIR",
        "expected_db_dir": "public_databases",
        "conda_env_config_key": "alphafold_conda_env",
    },
    "pdbfixer": {
        "display_name": "PDBFixer",
        "description": "PDB structure preprocessing (repair, cleanup, atom addition)",
        "download_url": "https://github.com/openmm/pdbfixer",
        "install_guide": """
conda install -c conda-forge pdbfixer openmm>=8.2

Or if conda is unavailable:
  pip install pdbfixer openmm
  (Note: pip install may fail on some platforms due to C++ extensions)
""".strip(),
        "expected_files": [],  # Python package, not a script
        "env_var": "",
        "config_key": "",
        "python_import": "pdbfixer",
    },
}


def _find_tool_in_conda_env(tool_name: str, env_name: str) -> str | None:
    """Try to locate a tool script inside a specific conda environment.

    Searches in this order:
      1. Editable installs (via Python import in the target env)
      2. Common filesystem locations under the conda env prefix
      3. User home and system-wide default paths

    Args:
        tool_name: Tool identifier.
        env_name: Conda environment name.

    Returns:
        Absolute path to the script if found, else None.
    """
    import subprocess

    # ── Strategy 1: editable-install detection via Python import ──
    # For packages installed with "pip install -e .", the code lives outside
    # the conda prefix. We run a tiny Python script in the target env to
    # locate the package directory and then infer the script path.

    editable_probes: dict[str, tuple[str, str]] = {
        "rfdiffusion": (
            "import rfdiffusion, os; print(os.path.dirname(rfdiffusion.__file__))",
            os.path.join("..", "scripts", "run_inference.py"),
        ),
        "proteinmpnn": (
            "import protein_mpnn_utils, os; print(os.path.dirname(protein_mpnn_utils.__file__))",
            os.path.join("..", "protein_mpnn_run.py"),
        ),
        "alphafold3": (
            "import importlib.util, os; "
            "spec = importlib.util.find_spec('alphafold3'); "
            "print(spec.origin if spec and spec.origin else '')",
            os.path.join("..", "run_alphafold.py"),
        ),
    }

    probe_code, rel_script = editable_probes.get(tool_name, ("", ""))
    if probe_code:
        try:
            proc = subprocess.run(
                ["conda", "run", "-n", env_name, "python", "-c", probe_code],
                capture_output=True, text=True, check=False, timeout=15,
            )
            if proc.returncode == 0:
                pkg_dir = proc.stdout.strip()
                if pkg_dir and os.path.isdir(pkg_dir):
                    candidate = os.path.normpath(
                        os.path.join(pkg_dir, rel_script)
                    )
                    if os.path.exists(candidate):
                        return os.path.abspath(candidate)
        except Exception:
            pass

    # ── Strategy 2: conda-prefix + fallback filesystem search ──
    try:
        proc = subprocess.run(
            ["conda", "run", "-n", env_name, "python", "-c",
             "import sys; print(sys.prefix)"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if proc.returncode != 0:
            return None
        env_prefix = proc.stdout.strip()
    except Exception:
        return None

    search_paths = []
    if tool_name == "rfdiffusion":
        search_paths = [
            os.path.join(env_prefix, "RFdiffusion", "scripts", "run_inference.py"),
            os.path.join(os.path.expanduser("~"), "RFdiffusion", "scripts", "run_inference.py"),
            "/opt/RFdiffusion/scripts/run_inference.py",
        ]
    elif tool_name == "proteinmpnn":
        search_paths = [
            os.path.join(env_prefix, "ProteinMPNN", "protein_mpnn_run.py"),
            os.path.join(os.path.expanduser("~"), "ProteinMPNN", "protein_mpnn_run.py"),
            "/opt/ProteinMPNN/protein_mpnn_run.py",
        ]
    elif tool_name == "alphafold3":
        search_paths = [
            os.path.join(env_prefix, "alphafold3", "run_alphafold.py"),
            os.path.join(env_prefix, "alphafold", "run_alphafold.py"),
            os.path.join(os.path.expanduser("~"), "alphafold3", "run_alphafold.py"),
            os.path.join(os.path.expanduser("~"), "alphafold", "run_alphafold.py"),
            "/opt/alphafold3/run_alphafold.py",
        ]

    for candidate in search_paths:
        if os.path.exists(candidate):
            return os.path.abspath(candidate)

    return None


def check_tool_status(tool_name: str) -> dict[str, Any]:
    """Check whether a specific tool is installed and detectable.

    Checks (in order):
      1. Configured path + conda env
      2. Current environment (PATH / default locations)
      3. Other known conda environments

    Args:
        tool_name: One of "rfdiffusion", "proteinmpnn", "alphafold3", "pdbfixer".

    Returns:
        Status dict with installed bool, path, conda_env, and metadata.
    """
    meta = TOOL_METADATA.get(tool_name)
    if not meta:
        return {"error": f"Unknown tool: {tool_name}"}

    result: dict[str, Any] = {
        "tool": tool_name,
        "display_name": meta["display_name"],
        "installed": False,
        "path": None,
        "conda_env": None,
        "download_url": meta["download_url"],
        "install_guide": meta["install_guide"],
    }

    # Special case: pdbfixer is a Python package, possibly in any conda env
    if tool_name == "pdbfixer":
        # Try current env first
        try:
            import pdbfixer  # noqa: F401
            result["installed"] = True
            result["path"] = "Python package (current env)"
            return result
        except ImportError:
            pass
        # Try common conda envs
        for env_name in ["protein-design", "BindCraft", "openmm", "base"]:
            try:
                import subprocess
                proc = subprocess.run(
                    ["conda", "run", "-n", env_name, "python", "-c",
                     "import pdbfixer; print('ok')"],
                    capture_output=True, text=True, check=False, timeout=10,
                )
                if proc.returncode == 0 and "ok" in proc.stdout:
                    result["installed"] = True
                    result["path"] = f"Python package (conda env: {env_name})"
                    result["conda_env"] = env_name
                    return result
            except Exception:
                continue
        return result

    # Script-based tools: try configured/current env first
    from mcp_server.tools import rfdiffusion, proteinmpnn, alphafold

    finders = {
        "rfdiffusion": rfdiffusion._find_rfdiffusion_script,
        "proteinmpnn": proteinmpnn._find_proteinmpnn_script,
        "alphafold3": alphafold._find_alphafold_script,
    }

    finder = finders.get(tool_name)
    if finder:
        try:
            path = finder()
            result["installed"] = True
            result["path"] = path
            # Infer conda_env from config if available
            conda_key = meta.get("conda_env_config_key")
            if conda_key:
                result["conda_env"] = getattr(CONFIG, conda_key, None)
        except FileNotFoundError:
            pass

    # If not found, scan other known conda environments
    if not result["installed"]:
        known_envs = ["protein-design", "SE3nv", "AF3", "alphafold3", "proteinmpnn"]
        for env_name in known_envs:
            found_path = _find_tool_in_conda_env(tool_name, env_name)
            if found_path:
                result["installed"] = True
                result["path"] = found_path
                result["conda_env"] = env_name
                break

    # AlphaFold3: also check genetic databases
    if tool_name == "alphafold3":
        from mcp_server.tools.alphafold import check_af3_database_status
        db_status = check_af3_database_status()
        result["database"] = db_status
        # If script is found but databases are missing, warn but don't block
        if result["installed"] and not db_status.get("detected"):
            result["note"] = (
                "AlphaFold3 script found, but genetic databases are missing. "
                "MSA search (run_data_pipeline) will fail if enabled. "
                "Install databases to ~/public_databases or configure db_dir. "
                "You can still run with run_data_pipeline=false for fast inference."
            )

    return result


def check_all_tools() -> dict[str, Any]:
    """Check status of all tools and return a summary.

    Returns:
        Dict with per-tool status and overall readiness.
    """
    tools = ["pdbfixer", "rfdiffusion", "proteinmpnn", "alphafold3"]
    results = {}
    all_ready = True
    alphafold_script_found_but_no_db = False

    for tool in tools:
        status = check_tool_status(tool)
        results[tool] = status
        if not status.get("installed", False):
            all_ready = False
            # Special flag for AlphaFold3: script exists but db missing
            if tool == "alphafold3" and status.get("path") and status.get("note"):
                alphafold_script_found_but_no_db = True

    message = "All tools are ready!"
    if not all_ready:
        if alphafold_script_found_but_no_db:
            message = (
                "AlphaFold3 script found but genetic databases are missing. "
                "Use configure_db_dir to set the database path, or download databases to ~/public_databases."
            )
        else:
            message = (
                "Some tools are missing. Use configure_tool_path to set paths, "
                "or follow the install guides above."
            )

    return {
        "all_ready": all_ready,
        "tools": results,
        "message": message,
    }


def configure_tool_path(tool_name: str, path: str, conda_env: str | None = None) -> dict[str, Any]:
    """Set the installation path for a tool and persist to config file.

    Args:
        tool_name: One of "rfdiffusion", "proteinmpnn", "alphafold3".
        path: Absolute path to the tool's root directory.
        conda_env: Optional conda environment name for this tool.

    Returns:
        Result dict with success status and validation info.
    """
    meta = TOOL_METADATA.get(tool_name)
    if not meta:
        return {"error": f"Unknown tool: {tool_name}", "supported": list(TOOL_METADATA.keys())}

    if tool_name == "pdbfixer":
        return {"error": "PDBFixer is installed via conda/pip, not a directory path. Run: conda install -c conda-forge pdbfixer"}

    # Validate path
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(abs_path):
        return {
            "error": f"Path does not exist or is not a directory: {abs_path}",
            "hint": "Please provide the directory containing the tool (e.g., /home/you/RFdiffusion)",
        }

    # Verify expected files exist
    missing_files = []
    for expected in meta["expected_files"]:
        expected_full = os.path.join(abs_path, expected)
        if not os.path.exists(expected_full):
            missing_files.append(expected)

    if missing_files:
        return {
            "error": f"Path exists but expected files are missing: {missing_files}",
            "provided_path": abs_path,
            "expected_files": meta["expected_files"],
            "hint": f"Make sure {meta['display_name']} is fully installed at this location.",
        }

    # Optionally validate conda environment
    conda_status = None
    if conda_env:
        from mcp_server.utils.conda_utils import check_conda_env
        conda_status = check_conda_env(conda_env)
        if not conda_status.get("exists"):
            return {
                "error": f"Conda environment '{conda_env}' not found",
                "conda_check": conda_status,
                "hint": "Create it first with: conda create -n <env> python=3.10",
            }

    # Persist to config file
    config_path = Path.home() / ".kimi-protein-design" / "config.yaml"
    config_data: dict[str, Any] = {}

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        except Exception:
            config_data = {}

    config_key = meta["config_key"]
    config_data[config_key] = abs_path

    # Also save conda_env if provided
    conda_config_key = meta.get("conda_env_config_key")
    if conda_env and conda_config_key:
        config_data[conda_config_key] = conda_env

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    # Update in-memory config
    setattr(CONFIG, config_key, abs_path)
    if conda_env and conda_config_key:
        setattr(CONFIG, conda_config_key, conda_env)

    logger.info("Configured %s path: %s (saved to %s)", tool_name, abs_path, config_path)

    result: dict[str, Any] = {
        "success": True,
        "tool": tool_name,
        "path": abs_path,
        "config_file": str(config_path),
        "message": f"{meta['display_name']} configured successfully at {abs_path}",
    }
    if conda_env:
        result["conda_env"] = conda_env
        result["conda_status"] = conda_status
    return result


def configure_db_dir(path: str) -> dict[str, Any]:
    """Configure the AlphaFold3 genetic database directory and persist it.

    Args:
        path: Absolute path to the databases directory (e.g., ~/public_databases).

    Returns:
        Result dict with success status and database status.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(abs_path):
        return {
            "error": f"Database directory does not exist: {abs_path}",
            "hint": "Provide the directory containing AlphaFold3 genetic databases (e.g., ~/public_databases)",
        }

    # Validate it looks like AF3 databases (warn but allow flat-file layouts)
    from mcp_server.tools.alphafold import _looks_like_af3_databases, check_af3_database_status
    db_status = check_af3_database_status(abs_path)
    if not db_status.get("detected"):
        return {
            "warning": f"Directory exists but does not look like AlphaFold3 databases: {abs_path}",
            "hint": "Expected subdirectories or files: bfd, mgy_clusters, pdb_seqres, rnacentral, uniprot, uniref90, nt. If you have a flat-file layout, you can proceed anyway.",
            "proceed_anyway": True,
            "database_status": db_status,
        }

    # Persist to config file
    config_path = Path.home() / ".kimi-protein-design" / "config.yaml"
    config_data: dict[str, Any] = {}

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        except Exception:
            config_data = {}

    config_data["db_dir"] = abs_path

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    # Update in-memory config
    CONFIG.db_dir = abs_path

    db_status = check_af3_database_status(abs_path)
    logger.info("Configured db_dir: %s (saved to %s)", abs_path, config_path)

    return {
        "success": True,
        "db_dir": abs_path,
        "config_file": str(config_path),
        "database_status": db_status,
        "message": f"AlphaFold3 database directory configured at {abs_path}",
    }


def get_missing_tool_prompt(tool_name: str) -> dict[str, Any]:
    """Generate a user-friendly prompt when a tool is missing.

    This is called from tool executors to produce actionable error messages
    that the Skill can surface to the user.

    Args:
        tool_name: The missing tool.

    Returns:
        Structured dict with error, install instructions, and next steps.
    """
    meta = TOOL_METADATA.get(tool_name)
    if not meta:
        return {"error": f"Unknown tool: {tool_name}"}

    next_steps = [
        f"1. Install {meta['display_name']}: {meta['download_url']}",
        f"2. Note the installation directory (e.g., ~/software/{meta['display_name']})",
        f"3. If the tool is in a conda environment, note the env name (e.g., '{meta.get('conda_env_example', 'myenv')}')",
        f"4. Configure the path by saying: 'Set {tool_name} path to /your/install/dir'",
        "   Or use the configure_tool_path tool directly.",
    ]

    # AlphaFold3 special case: also mention databases
    if tool_name == "alphafold3":
        next_steps.extend([
            "5. Download genetic databases (e.g., to ~/public_databases)",
            "6. Configure database path: 'Set AlphaFold3 db_dir to ~/public_databases'",
            "   Or use the configure_db_dir tool directly.",
        ])

    return {
        "error": f"{meta['display_name']} is not installed or not found",
        "tool": tool_name,
        "display_name": meta["display_name"],
        "description": meta["description"],
        "download_url": meta["download_url"],
        "install_guide": meta["install_guide"],
        "next_steps": next_steps,
        "quick_config": {
            "tool": tool_name,
            "example_command": f"configure_tool_path(tool='{tool_name}', path='/path/to/{tool_name}', conda_env='{meta.get('conda_env_example', '')}')",
        },
    }
