"""Configuration management for the protein design MCP server.

Reads settings from environment variables and optional config file
(~/.protein-design/config.yaml, with fallback to ~/.kimi-protein-design/).
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None  # Graceful fallback when PyYAML is not installed

logger = logging.getLogger(__name__)


@dataclass
class ProteinDesignConfig:
    """Configuration for protein design pipeline."""

    # Output settings
    output_dir: str = "/tmp/protein-design"
    max_jobs: int = 4
    timeout: int = 3600  # seconds

    # GPU settings
    cuda_visible_devices: Optional[str] = None

    # Tool paths (auto-detected or user-configured)
    rfdiffusion_path: Optional[str] = None
    proteinmpnn_path: Optional[str] = None
    alphafold_path: Optional[str] = None

    # AlphaFold3 genetic databases directory
    db_dir: Optional[str] = None

    # Conda environment names for each tool (optional)
    # If set, commands are wrapped with `conda run -n <env>`
    rfdiffusion_conda_env: Optional[str] = None
    proteinmpnn_conda_env: Optional[str] = None
    alphafold_conda_env: Optional[str] = None

    def __post_init__(self):
        """Mark that output directory needs to be ensured before use."""
        self._output_dir_ensured = False


def load_config() -> ProteinDesignConfig:
    """Load configuration from environment variables and config file.

    Priority: env vars > config file > defaults.

    Returns:
        ProteinDesignConfig instance with resolved settings.
    """
    config = ProteinDesignConfig()

    # Override from environment variables
    if env_output := os.environ.get("PROTEIN_DESIGN_OUTPUT_DIR"):
        config.output_dir = env_output

    if env_max_jobs := os.environ.get("PROTEIN_DESIGN_MAX_JOBS"):
        try:
            config.max_jobs = int(env_max_jobs)
        except ValueError:
            pass

    if env_timeout := os.environ.get("PROTEIN_DESIGN_TIMEOUT"):
        try:
            config.timeout = int(env_timeout)
        except ValueError:
            pass

    if env_cuda := os.environ.get("CUDA_VISIBLE_DEVICES"):
        config.cuda_visible_devices = env_cuda

    if env_rfd := os.environ.get("RFDIFFUSION_PATH"):
        config.rfdiffusion_path = env_rfd

    if env_mpnn := os.environ.get("PROTEINMPNN_PATH"):
        config.proteinmpnn_path = env_mpnn

    if env_af := os.environ.get("ALPHAFOLD_PATH"):
        config.alphafold_path = env_af

    if env_db := os.environ.get("PROTEIN_DESIGN_DB_DIR"):
        config.db_dir = env_db

    if env_rfd_conda := os.environ.get("RFDIFFUSION_CONDA_ENV"):
        config.rfdiffusion_conda_env = env_rfd_conda

    if env_mpnn_conda := os.environ.get("PROTEINMPNN_CONDA_ENV"):
        config.proteinmpnn_conda_env = env_mpnn_conda

    if env_af_conda := os.environ.get("ALPHAFOLD_CONDA_ENV"):
        config.alphafold_conda_env = env_af_conda

    # Override from config file (lowest priority after defaults).
    # Check new path first, fall back to legacy path for backward compatibility.
    config_path = Path.home() / ".protein-design" / "config.yaml"
    legacy_config_path = Path.home() / ".kimi-protein-design" / "config.yaml"
    if not config_path.exists() and legacy_config_path.exists():
        config_path = legacy_config_path
    if config_path.exists():
        if yaml is None:
            logger.warning("PyYAML not installed; cannot read config file %s", config_path)
        else:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_config = yaml.safe_load(f) or {}

                for key, value in file_config.items():
                    if hasattr(config, key) and value is not None:
                        setattr(config, key, value)
            except Exception as exc:
                logger.warning("Failed to parse config file %s: %s", config_path, exc)

    # Ensure output directory exists (lazy: only when config is actually used)
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    return config


# Global config instance
CONFIG = load_config()
