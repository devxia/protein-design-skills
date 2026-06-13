"""Tests for pure helper functions in protein_design/hooks/*.py."""
import importlib.util
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_hook_module(name: str):
    """Load a hook module whose filename contains hyphens."""
    file_path = _PROJECT_ROOT / "protein_design" / "hooks" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_cost_estimator = _load_hook_module("cost-estimator")


def test_detect_pipeline_defaults():
    pipeline = _cost_estimator._detect_pipeline("Design a binder")
    assert pipeline["num_designs"] == 10
    assert pipeline["stage1"] == "rfdiffusion"
    assert pipeline["stage2"] == "proteinmpnn"
    assert pipeline["stage3"] == "alphafold3"


def test_detect_pipeline_num_designs():
    pipeline = _cost_estimator._detect_pipeline("I want 50 designs of a binder")
    assert pipeline["num_designs"] == 50


def test_detect_pipeline_alternatives():
    assert _cost_estimator._detect_pipeline("Use boltz for validation")["stage3"] == "boltz"
    assert _cost_estimator._detect_pipeline("foldflow backbone")["stage1"] == "foldflow"
    assert _cost_estimator._detect_pipeline("esmfold screening")["stage3"] == "esmfold"


def test_estimate_cost_basic():
    pipeline = {"num_designs": 10, "stage1": "rfdiffusion", "stage2": "proteinmpnn", "stage3": "alphafold3"}
    cost = _cost_estimator._estimate_cost(pipeline)
    assert cost["num_designs"] == 10
    assert cost["max_gpu_memory_gb"] == 40
    assert cost["needs_databases"] is True
    assert cost["total_time_min"] > 0


def test_estimate_cost_unknown_stage_uses_default():
    pipeline = {"num_designs": 5, "stage1": "nonexistent", "stage2": "nonexistent", "stage3": "nonexistent"}
    cost = _cost_estimator._estimate_cost(pipeline)
    assert cost["num_designs"] == 5
    assert cost["total_time_min"] > 0
