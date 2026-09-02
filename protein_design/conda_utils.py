"""Shared helpers for cross-conda tool execution.

Many external protein-design tools (RFdiffusion, ProteinMPNN, AlphaFold3, ...)
live in dedicated conda environments.  Rather than activating/deactivating
shells, the standalone scripts in ``scripts/`` invoke tools via
``conda run -n <env> ...``.  This module centralises that logic so it does not
have to be duplicated across every runner.

It intentionally contains no heavy ML dependencies.

Usage::

    from protein_design.conda_utils import find_conda_env, build_tool_command

    env = find_conda_env(["rfdiffusion", "SE3nv"], "import rfdiffusion")
    if env is not None:
        cmd = build_tool_command(f"conda run -n {env} python -m rfdiffusion")
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional


def resolve_configured_path(value: Any, entrypoints: list[str]) -> Optional[str]:
    """Resolve a configured tool file or a directory's known entry point.

    A configured file is returned as-is, while a configured directory is only
    accepted when one of the caller-provided, tool-specific ``entrypoints``
    exists below it.  This keeps generic names such as ``run.py`` from being
    guessed for an unrelated checkout.
    """
    if not isinstance(value, (str, Path)):
        return None
    raw_value = str(value).strip()
    if not raw_value:
        return None

    path = Path(raw_value).expanduser()
    if not path.exists():
        return None
    if path.is_dir():
        for entrypoint in entrypoints:
            candidate = path / entrypoint
            if candidate.is_file():
                return str(candidate)
        return None
    if path.is_file():
        return str(path)
    return None


def find_conda_env(envs: list[str], import_check: str, timeout: int = 10) -> Optional[str]:
    """Return the first conda env name where ``import_check`` succeeds.

    Probes each candidate environment by running
    ``conda run -n <env> python -c "<import_check>"``.  The first environment
    whose probe exits 0 is returned.

    Args:
        envs: Candidate conda environment names, tried in order.
        import_check: Python source executed under ``-c`` to verify the tool is
            importable (e.g. ``"import rfdiffusion"``).
        timeout: Seconds to wait for each probe before giving up on that env.

    Returns:
        The name of the first matching environment, or ``None`` if none match
        or ``conda`` is unavailable.
    """
    for env in envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env, "python", "-c", import_check],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                return env
        except (subprocess.TimeoutExpired, OSError):
            continue
    return None


def probe_conda_envs(
    envs: list[str],
    probe_args: list[str],
    require_stdout: bool = False,
    timeout: int = 10,
) -> Optional[str]:
    """Return the first conda env where a probe command succeeds.

    Runs ``conda run -n <env> <probe_args...>`` for each candidate.  The first
    environment whose probe exits 0 (and, when ``require_stdout`` is set, also
    produces non-empty stdout) is returned.

    A probe expressed as ``["which", <name>]`` is converted to a Python
    ``shutil.which`` probe.  This avoids relying on a POSIX ``which`` command
    inside conda environments and keeps discovery portable on Windows.

    Args:
        envs: Candidate conda environment names, tried in order.
        probe_args: Arguments appended after ``conda run -n <env>``.
        require_stdout: When True, also require non-empty stdout from the probe.
        timeout: Seconds to wait for each probe before giving up on that env.

    Returns:
        The name of the first matching environment, or ``None``.
    """
    if len(probe_args) == 2 and probe_args[0] == "which":
        probe_args = [
            "python",
            "-c",
            "import shutil, sys; "
            "path = shutil.which(sys.argv[1]); "
            "print(path or ''); "
            "sys.exit(0 if path else 1)",
            probe_args[1],
        ]

    for env in envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env] + probe_args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                if not require_stdout or result.stdout.strip():
                    return env
        except (subprocess.TimeoutExpired, OSError):
            continue
    return None


def is_conda_command(command: str) -> bool:
    """Return True if ``command`` is a ``conda run`` or ``conda_api:`` marker."""
    if command.startswith("conda_api:"):
        return True
    # Token-level check so "conda runner ..." is not mistaken for "conda run".
    return command.split()[:2] == ["conda", "run"]


def is_bare_executable(command: str) -> bool:
    """Return True if ``command`` is a bare CLI executable name.

    A bare executable is a single token with no path separators, not starting
    with ``python`` or ``conda``.  This helper is retained for callers that
    explicitly know a command is a PATH-resolved console executable.
    """
    if not command:
        return False
    if " " in command or "/" in command or "\\" in command:
        return False
    if command.startswith(("python", "conda")):
        return False
    return True


def parse_conda_api(command: str) -> Optional[str]:
    """Extract the env name from a ``conda_api:<env>`` marker string.

    Returns ``None`` if ``command`` is not a ``conda_api:`` marker. The env
    name is stripped of surrounding whitespace; a marker with an empty name
    (e.g. ``"conda_api:"``) returns an empty string, which
    :func:`build_tool_command` rejects as malformed.
    """
    if command.startswith("conda_api:"):
        return command.split(":", 1)[1].strip()
    return None


def build_tool_command(
    command: str,
    wrapper_script: Optional[str] = None,
    bare_executable: bool = False,
) -> list[str]:
    """Convert a tool command string into an argv list for ``subprocess.run``.

    Recognised command formats:

    * ``"conda run -n <env> ..."`` — split on whitespace into an argv list.
    * ``"conda_api:<env>"`` — a marker indicating the tool should be run via
      ``conda run -n <env> python``; expanded to ``["conda", "run", "-n",
      <env>, "python"]``.
    * A Python invocation such as ``"python -m <module>"`` or one beginning
      with an absolute interpreter path — split into an argv list. Quoted
      interpreter paths containing spaces remain a single token.
    * A ``.py`` script path — run as ``["python", <command>]``.
    * A console executable (a bare name or an explicit path, including paths
      containing spaces) — used directly as ``[<command>]``.  This is for CLI
      binaries such as ``"boltz"`` and ``"/opt/bin/boltz"``.

    When ``wrapper_script`` is provided, it is prepended to the argv list as an
    escape hatch for complex environment setup that ``conda run`` cannot handle
    (e.g. sourcing custom activation scripts).  The wrapper receives the
    original command as its arguments.

    Args:
        command: Tool command string produced by a runner's ``find_*`` helper.
        wrapper_script: Optional path to a shell script that wraps the command.
        bare_executable: Deprecated compatibility hint.  Console executables
            are now detected automatically; when set, ``command`` is still
            used directly.

    Returns:
        An argv list suitable for ``subprocess.run(..., shell=False)``.

    Raises:
        ValueError: If ``command`` is a ``conda_api:`` marker with an empty
            env name, or is empty/whitespace-only.
    """
    command = command.strip()
    if not command:
        raise ValueError(f"Empty tool command: {command!r}")
    api_env = parse_conda_api(command)
    if api_env is not None:
        if not api_env:
            raise ValueError(f"conda_api: marker has an empty env name: {command!r}")
        argv = ["conda", "run", "-n", api_env, "python"]
    elif is_conda_command(command):
        argv = shlex.split(command)
    else:
        split_tokens = shlex.split(command)
        if not split_tokens:
            raise ValueError(f"Empty tool command: {command!r}")

        # An unquoted executable or script path may itself contain spaces. Keep
        # that path intact, while still tokenising module invocations built with
        # ``shlex.join([sys.executable, "-m", module])``. The latter can begin
        # with any absolute Python executable, not only a binary named exactly
        # ``python`` or ``python3``.
        is_python_module_invocation = (
            len(split_tokens) >= 3 and split_tokens[1] == "-m"
        )
        is_unquoted_path = (
            ("/" in command or "\\" in command)
            and not command.startswith(("'", '"'))
        )
        if bare_executable or (is_unquoted_path and not is_python_module_invocation):
            tokens = [command]
        else:
            tokens = split_tokens

        first_token = tokens[0]
        is_script_path = len(tokens) == 1 and first_token.lower().endswith(".py")
        if is_script_path:
            argv = ["python", first_token]
        else:
            # Console executables, including explicit paths, must not be
            # handed to Python.
            argv = tokens

    if wrapper_script:
        return [wrapper_script] + argv
    return argv


def resolve_wrapper_script(config: dict[str, Any], tool_key: str) -> Optional[str]:
    """Look up a per-tool ``wrapper_script`` from config, if set.

    The config key is ``<tool_key>_wrapper_script`` (e.g.
    ``rfdiffusion_wrapper_script``).  An empty/missing value returns ``None``.

    Args:
        config: Config dict from ``protein_design.utils.get_config``.
        tool_key: Lower-snake tool identifier (e.g. ``"rfdiffusion"``).

    Returns:
        The wrapper script path or ``None``.
    """
    value = config.get(f"{tool_key}_wrapper_script")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
