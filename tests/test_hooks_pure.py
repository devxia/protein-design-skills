"""Tests for pure helper functions in protein_design/hooks/*.py."""
from tests.helpers import load_hook_module as _load_hook_module


_cost_estimator = _load_hook_module("cost-estimator")
_quality_gate = _load_hook_module("quality-gate")
_gpu_check = _load_hook_module("gpu-check-hook")


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


def test_quality_gate_fails_below_threshold():
    metrics = {"plddt": 50.0, "ptm": 0.5}
    evaluation = _quality_gate._evaluate_quality(metrics, "monomer")
    assert evaluation["is_passing"] is False
    assert any("plddt" in f for f in evaluation["failed"])
    assert any("ptm" in f for f in evaluation["failed"])


def test_quality_gate_passes_above_threshold():
    metrics = {"plddt": 90.0, "ptm": 0.9}
    evaluation = _quality_gate._evaluate_quality(metrics, "monomer")
    assert evaluation["is_passing"] is True


def test_quality_gate_ignores_absent_metrics():
    # A binder missing ipTM should still be evaluated on the metrics present.
    metrics = {"plddt": 90.0}
    evaluation = _quality_gate._evaluate_quality(metrics, "binder")
    assert evaluation["is_passing"] is True


def test_quality_gate_fails_closed_with_no_evaluable_metrics():
    # Metrics matching none of the design type's thresholds must not pass (#19).
    metrics = {"iptm": 0.95}
    evaluation = _quality_gate._evaluate_quality(metrics, "monomer")
    assert evaluation["is_passing"] is False
    assert evaluation["no_metrics_evaluated"] is True


def test_health_check_probes_run_concurrently(monkeypatch):
    """Ten 2s probes must finish within the 5s hook budget, i.e. run in parallel (#29)."""
    import time

    module = _load_hook_module("session-health-check")

    def slow_run(cmd, **kwargs):
        time.sleep(2)

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(module.subprocess, "run", slow_run)
    start = time.time()
    tools = module._check_tools()
    elapsed = time.time() - start
    assert elapsed < 5, f"probes appear sequential: {elapsed:.1f}s"
    assert len(tools) == 10
    assert all(v == "✓" for v in tools.values())


def test_gpu_check_fails_open_when_nvidia_smi_missing(monkeypatch):
    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(_gpu_check.subprocess, "run", raise_file_not_found)
    ok, _msg = _gpu_check.check_gpu()
    assert ok is True
