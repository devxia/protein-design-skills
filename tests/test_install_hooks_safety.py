"""Regression tests: legacy codex cleanup must only delete installer-managed files (#31)."""

from __future__ import annotations

from pathlib import Path

from tests.helpers import load_install_hooks_module

ih = load_install_hooks_module()


def _fake_legacy_env(tmp_path, monkeypatch) -> Path:
    """Point the legacy codex locations at a throwaway directory tree."""
    hooks_dir = tmp_path / ".codex" / "hooks"
    hooks_dir.mkdir(parents=True)
    monkeypatch.setattr(ih, "LEGACY_CODEX_HOOKS_DIR", hooks_dir)
    monkeypatch.setattr(ih, "LEGACY_CODEX_SETTINGS", tmp_path / ".codex" / "settings.json")
    return hooks_dir


def test_cleanup_preserves_user_protein_named_file(tmp_path, monkeypatch):
    """A user file merely containing 'protein' in its name must survive."""
    hooks_dir = _fake_legacy_env(tmp_path, monkeypatch)
    user_file = hooks_dir / "my_protein_analysis.py"
    user_file.write_text("# the user's own analysis script\n", encoding="utf-8")

    removed = ih._uninstall_codex(tmp_path / "hooks.json")

    assert user_file.exists()
    assert removed is False


def test_cleanup_removes_only_managed_files(tmp_path, monkeypatch):
    """Canonical hook names and marker-tagged files are removed; bystanders survive."""
    hooks_dir = _fake_legacy_env(tmp_path, monkeypatch)
    managed = hooks_dir / "quality-gate.py"
    managed.write_text("# legacy copy of an installed hook\n", encoding="utf-8")
    marker_file = hooks_dir / "renamed_copy.py"
    marker_file.write_text(
        f"# {ih.PROTEIN_DESIGN_MARKER} start\n# ...\n# {ih.PROTEIN_DESIGN_MARKER} end\n",
        encoding="utf-8",
    )
    bystander = hooks_dir / "random_tool.py"
    bystander.write_text("print('not ours')\n", encoding="utf-8")

    removed = ih._uninstall_codex(tmp_path / "hooks.json")

    assert not managed.exists()
    assert not marker_file.exists()
    assert bystander.exists()
    assert removed is True


def test_windows_command_rewrite_rejects_expansion_characters_in_project_path(tmp_path):
    """cmd.exe expansion characters must not enter generated hook commands."""
    root = tmp_path / "project%USERPROFILE%"
    hook_dir = root / "protein_design" / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "quality-gate.py").write_text("# hook\n", encoding="utf-8")
    source = {
        "hooks": {
            "PostToolUse": [{
                "matcher": "PowerShell",
                "hooks": [{
                    "command": 'python "${PLUGIN_ROOT}/protein_design/hooks/quality-gate.py"'
                }],
            }]
        }
    }
    import pytest

    with pytest.raises(ValueError, match="unsafe expansion"):
        ih._rewrite_hook_commands(source, root, platform="win32")
