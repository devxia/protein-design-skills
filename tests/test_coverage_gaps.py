"""Coverage-gap regression tests (batch 3).

- Every hook command in the declarative manifests points at a real .py file.
- install-hooks._resolve_hook_script path-escape / metacharacter validation.
- read_hook_input contract: empty stdin -> {}, invalid JSON -> JSONDecodeError.
"""
from __future__ import annotations

import io
import json
import re

import pytest

from protein_design.utils import read_hook_input
from tests.helpers import PROJECT_ROOT, load_hook_module


# ---------------------------------------------------------------------------
# Declared hook scripts must exist
# ---------------------------------------------------------------------------


def _collect_hook_commands() -> list[str]:
    commands: list[str] = []

    def _walk(node) -> None:
        if isinstance(node, dict):
            cmd = node.get("command")
            if isinstance(cmd, str):
                commands.append(cmd)
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)

    hooks_json = json.loads((PROJECT_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    _walk(hooks_json)
    manifest = json.loads((PROJECT_ROOT / "kimi.plugin.json").read_text(encoding="utf-8"))
    _walk(manifest)
    return commands


def test_every_declared_hook_script_exists():
    """Renaming/removing a hook .py without updating manifests must fail CI."""
    commands = _collect_hook_commands()
    assert len(commands) >= 22, "expected at least the 22 canonical hooks"
    for cmd in commands:
        match = re.search(r'(\S+\.py)', cmd)
        assert match, f"no .py target in command: {cmd!r}"
        rel = match.group(1)
        rel = rel.replace("${CLAUDE_PLUGIN_ROOT}", "").replace("${PLUGIN_ROOT}", "")
        rel = rel.lstrip("./")
        assert (PROJECT_ROOT / rel).exists(), f"missing hook script {rel!r} (command: {cmd!r})"


# ---------------------------------------------------------------------------
# install-hooks._resolve_hook_script security validation
# ---------------------------------------------------------------------------

_installer = load_hook_module("install-hooks")


def test_resolve_hook_script_accepts_placeholder_path():
    resolved = _installer._resolve_hook_script(
        "${CLAUDE_PLUGIN_ROOT}/protein_design/hooks/tool-recommender.py", PROJECT_ROOT
    )
    assert resolved == (PROJECT_ROOT / "protein_design" / "hooks" / "tool-recommender.py").resolve()


def test_resolve_hook_script_rejects_directory_escape(tmp_path):
    with pytest.raises(ValueError, match="outside allowed directory"):
        _installer._resolve_hook_script("../../../etc/passwd", tmp_path)


def test_resolve_hook_script_rejects_shell_metacharacters():
    with pytest.raises(ValueError, match="forbidden characters"):
        _installer._resolve_hook_script(
            "${CLAUDE_PLUGIN_ROOT}/protein_design/hooks/x.py; rm -rf /", PROJECT_ROOT
        )


def test_resolve_hook_script_allows_project_root_with_special_chars(tmp_path):
    """A project root containing '&' or '(' is legitimate; only the declared
    script argument is screened for metacharacters."""
    root = tmp_path / "weird & (root)"
    (root / "protein_design" / "hooks").mkdir(parents=True)
    (root / "protein_design" / "hooks" / "h.py").write_text("# hook\n", encoding="utf-8")
    resolved = _installer._resolve_hook_script(
        "${CLAUDE_PLUGIN_ROOT}/protein_design/hooks/h.py", root
    )
    assert resolved.exists()


# ---------------------------------------------------------------------------
# read_hook_input contract
# ---------------------------------------------------------------------------


def test_read_hook_input_empty_stdin_returns_empty_dict(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert read_hook_input() == {}


def test_read_hook_input_whitespace_stdin_returns_empty_dict(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("   \n"))
    assert read_hook_input() == {}


def test_read_hook_input_invalid_json_raises(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    with pytest.raises(json.JSONDecodeError):
        read_hook_input()


def test_read_hook_input_dict_passthrough(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"prompt": "hi"}'))
    assert read_hook_input() == {"prompt": "hi"}
