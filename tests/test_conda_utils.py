"""Tests for protein_design.conda_utils helpers."""

from __future__ import annotations

from protein_design.conda_utils import (
    build_tool_command,
    find_conda_env,
    is_bare_executable,
    is_conda_command,
    parse_conda_api,
    probe_conda_envs,
    resolve_wrapper_script,
)


# ---------------------------------------------------------------------------
# is_conda_command / parse_conda_api
# ---------------------------------------------------------------------------


def test_is_conda_command_recognises_conda_run() -> None:
    assert is_conda_command("conda run -n rfdiff python -m rfdiffusion") is True


def test_is_conda_command_recognises_conda_api_marker() -> None:
    assert is_conda_command("conda_api:esmfold") is True


def test_is_conda_command_rejects_plain_path() -> None:
    assert is_conda_command("/usr/local/bin/tool") is False


def test_parse_conda_api_extracts_env() -> None:
    assert parse_conda_api("conda_api:myenv") == "myenv"


def test_parse_conda_api_returns_none_for_non_marker() -> None:
    assert parse_conda_api("conda run -n x") is None
    assert parse_conda_api("/path/to/script.py") is None


# ---------------------------------------------------------------------------
# build_tool_command
# ---------------------------------------------------------------------------


def test_build_tool_command_splits_conda_run() -> None:
    assert build_tool_command("conda run -n rfdiff python -m rfdiffusion") == [
        "conda",
        "run",
        "-n",
        "rfdiff",
        "python",
        "-m",
        "rfdiffusion",
    ]


def test_build_tool_command_expands_conda_api_marker() -> None:
    assert build_tool_command("conda_api:esmfold") == [
        "conda",
        "run",
        "-n",
        "esmfold",
        "python",
    ]


def test_build_tool_command_wraps_plain_path_with_python() -> None:
    assert build_tool_command("/opt/tool/run.py") == ["python", "/opt/tool/run.py"]


def test_build_tool_command_prepends_wrapper_script() -> None:
    cmd = build_tool_command(
        "conda run -n rfdiff python -m rfdiffusion",
        wrapper_script="/home/user/wrap.sh",
    )
    assert cmd[0] == "/home/user/wrap.sh"
    assert cmd[1:] == ["conda", "run", "-n", "rfdiff", "python", "-m", "rfdiffusion"]


def test_build_tool_command_wrapper_with_conda_api() -> None:
    cmd = build_tool_command("conda_api:esmfold", wrapper_script="/w.sh")
    assert cmd == ["/w.sh", "conda", "run", "-n", "esmfold", "python"]


def test_build_tool_command_splits_python_module_invocation() -> None:
    assert build_tool_command("python -m pdbfixer") == ["python", "-m", "pdbfixer"]


def test_build_tool_command_bare_executable_runs_directly() -> None:
    # A bare CLI name found via `which` must NOT be prefixed with "python",
    # otherwise Python would treat the executable name as a script path.
    assert build_tool_command("boltz", bare_executable=True) == ["boltz"]


def test_build_tool_command_bare_executable_with_wrapper() -> None:
    cmd = build_tool_command("omegafold", wrapper_script="/w.sh", bare_executable=True)
    assert cmd == ["/w.sh", "omegafold"]


# ---------------------------------------------------------------------------
# is_bare_executable
# ---------------------------------------------------------------------------


def test_is_bare_executable_true_for_simple_name() -> None:
    assert is_bare_executable("boltz") is True
    assert is_bare_executable("chai-lab") is True
    assert is_bare_executable("omegafold") is True


def test_is_bare_executable_false_for_path() -> None:
    assert is_bare_executable("/usr/local/bin/boltz") is False
    assert is_bare_executable("./boltz") is False


def test_is_bare_executable_false_for_python_prefix() -> None:
    assert is_bare_executable("python -m boltz") is False
    assert is_bare_executable("python") is False


def test_is_bare_executable_false_for_conda() -> None:
    assert is_bare_executable("conda run -n x boltz") is False
    assert is_bare_executable("conda_api:esmfold") is False


def test_is_bare_executable_false_for_empty() -> None:
    assert is_bare_executable("") is False


# ---------------------------------------------------------------------------
# resolve_wrapper_script
# ---------------------------------------------------------------------------


def test_resolve_wrapper_script_returns_value_when_set() -> None:
    config = {"rfdiffusion_wrapper_script": "/home/user/wrap.sh"}
    assert resolve_wrapper_script(config, "rfdiffusion") == "/home/user/wrap.sh"


def test_resolve_wrapper_script_returns_none_when_missing() -> None:
    assert resolve_wrapper_script({}, "rfdiffusion") is None


def test_resolve_wrapper_script_returns_none_for_empty_string() -> None:
    config = {"rfdiffusion_wrapper_script": "  "}
    assert resolve_wrapper_script(config, "rfdiffusion") is None


def test_resolve_wrapper_script_returns_none_for_non_string() -> None:
    config = {"rfdiffusion_wrapper_script": 0}
    assert resolve_wrapper_script(config, "rfdiffusion") is None


# ---------------------------------------------------------------------------
# find_conda_env / probe_conda_envs — conda is not available in CI, so these
# exercise the "conda binary missing" path via FileNotFoundError. They guard
# against regressions in the probe loop and exception handling.
# ---------------------------------------------------------------------------


def test_find_conda_env_returns_none_when_conda_missing(monkeypatch) -> None:
    import protein_design.conda_utils as cu

    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("conda")

    monkeypatch.setattr(cu.subprocess, "run", raise_file_not_found)
    assert find_conda_env(["rfdiffusion", "protein-design"], "import rfdiffusion") is None


def test_probe_conda_envs_returns_none_when_conda_missing(monkeypatch) -> None:
    import protein_design.conda_utils as cu

    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("conda")

    monkeypatch.setattr(cu.subprocess, "run", raise_file_not_found)
    assert probe_conda_envs(["boltz"], ["boltz", "--help"]) is None
