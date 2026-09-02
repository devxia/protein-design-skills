"""Tests for the Claude Code installer in protein_design/hooks/install-hooks.py.

Covers the nested settings.json hook schema, preservation of foreign hooks,
migration of legacy flat entries, --force deduplication, exit-code
propagation from install_hooks(), and _count_protein_hooks() layout
detection.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.helpers import load_install_hooks_module

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ih = load_install_hooks_module()

HOOKS_CONFIG = {
    "hooks": {
        "UserPromptSubmit": [
            {
                "matcher": "(?i)protein",
                "hooks": [
                    {
                        "type": "command",
                        "command": "/usr/bin/python /repo/protein_design/hooks/user-onboarding.py",
                        "statusMessage": "Protein design: User Onboarding",
                        "timeout": 5,
                    },
                    {
                        "type": "command",
                        "command": "/usr/bin/python /repo/protein_design/hooks/session-health-check.py",
                        "timeout": 5,
                    },
                ],
            }
        ],
        "PreToolUse": [
            {
                "matcher": "run_.*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "/usr/bin/python /repo/protein_design/hooks/gpu-check-hook.py",
                        "timeout": 10,
                    }
                ],
            }
        ],
    }
}

OUR_COMMANDS = [
    "/usr/bin/python /repo/protein_design/hooks/user-onboarding.py",
    "/usr/bin/python /repo/protein_design/hooks/session-health-check.py",
    "/usr/bin/python /repo/protein_design/hooks/gpu-check-hook.py",
]


def _install(tmp_path: Path, force: bool = False) -> dict:
    config_path = tmp_path / "settings.json"
    ih._install_claude(config_path, HOOKS_CONFIG, force=force)
    return json.loads(config_path.read_text(encoding="utf-8"))


def _all_hook_commands(settings: dict) -> list[str]:
    commands = []
    for groups in settings["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                commands.append(hook["command"])
    return commands


def test_install_claude_writes_nested_schema(tmp_path):
    """Hooks must be written in Claude Code's nested event schema."""
    settings = _install(tmp_path)

    hooks = settings["hooks"]
    assert isinstance(hooks, dict), "hooks must map event names to matcher groups"
    assert set(hooks) == {"UserPromptSubmit", "PreToolUse"}

    group = hooks["UserPromptSubmit"][0]
    assert group["matcher"] == "(?i)protein"
    assert [h["command"] for h in group["hooks"]] == OUR_COMMANDS[:2]
    for hook in group["hooks"]:
        assert hook["type"] == "command"
        assert hook["timeout"] == 5
    # Extra fields from the canonical config (e.g. statusMessage) survive.
    assert group["hooks"][0]["statusMessage"] == "Protein design: User Onboarding"

    pre_group = hooks["PreToolUse"][0]
    assert pre_group["matcher"] == "run_.*"
    assert pre_group["hooks"][0]["timeout"] == 10
    # No legacy flat entries anywhere.
    assert all(isinstance(groups, list) for groups in hooks.values())


def test_install_claude_preserves_foreign_hooks_and_settings(tmp_path):
    """Foreign hooks and unrelated settings keys must survive the merge."""
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "model": "opus",
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {"type": "command", "command": "/usr/bin/python /other/lint.py", "timeout": 30}
                            ],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    settings = _install(tmp_path)

    assert settings["model"] == "opus"
    groups = settings["hooks"]["PreToolUse"]
    bash_groups = [g for g in groups if g["matcher"] == "Bash"]
    assert len(bash_groups) == 1
    assert bash_groups[0]["hooks"][0]["command"] == "/usr/bin/python /other/lint.py"
    # Our hooks are registered alongside, in their own matcher group.
    our_groups = [g for g in groups if g["matcher"] == "run_.*"]
    assert len(our_groups) == 1


def test_install_claude_idempotent_without_force(tmp_path):
    """A non-force rerun over an up-to-date nested config adds nothing."""
    first = _install(tmp_path)
    second = _install(tmp_path)

    assert _all_hook_commands(second) == _all_hook_commands(first)
    assert len(_all_hook_commands(second)) == 3


def test_install_claude_force_does_not_duplicate(tmp_path):
    """Repeated --force reinstalls must not grow the hook list."""
    _install(tmp_path, force=True)
    second = _install(tmp_path, force=True)

    commands = _all_hook_commands(second)
    assert len(commands) == len(set(commands)) == 3


def test_install_claude_migrates_legacy_flat_entries(tmp_path):
    """Legacy flat entries are folded into the nested layout; ours are refreshed."""
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "hooks": [
                    {
                        "event": "UserPromptSubmit",
                        "matcher": "(?i)protein",
                        "command": "/old/python /old/repo/protein_design/hooks/user-onboarding.py",
                        "timeout": 5,
                    },
                    {
                        "event": "UserPromptSubmit",
                        "matcher": "",
                        "command": "/usr/bin/python /other/user-hook.py",
                        "timeout": 5,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    settings = _install(tmp_path)

    assert isinstance(settings["hooks"], dict)
    commands = _all_hook_commands(settings)
    # Stale flat entry with the old path is gone; current commands registered.
    assert "/old/python /old/repo/protein_design/hooks/user-onboarding.py" not in commands
    assert OUR_COMMANDS[0] in commands
    # Foreign flat entry is preserved (folded into the nested layout).
    assert "/usr/bin/python /other/user-hook.py" in commands
    assert len(commands) == 4  # 3 ours + 1 foreign


def test_install_claude_force_cleans_legacy_flat_entries(tmp_path):
    """--force over a legacy flat install registers each hook exactly once."""
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "hooks": [
                    {
                        "event": "UserPromptSubmit",
                        "matcher": "(?i)protein",
                        "command": OUR_COMMANDS[0],
                        "timeout": 5,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    settings = _install(tmp_path, force=True)

    commands = _all_hook_commands(settings)
    assert commands.count(OUR_COMMANDS[0]) == 1
    assert len(commands) == 3


def test_uninstall_claude_removes_nested_hooks_only(tmp_path):
    """Uninstall removes our nested hooks and keeps foreign ones."""
    config_path = tmp_path / "settings.json"
    _install(tmp_path)
    settings = json.loads(config_path.read_text(encoding="utf-8"))
    settings["hooks"]["PreToolUse"].append(
        {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": "/usr/bin/python /other/lint.py"}],
        }
    )
    config_path.write_text(json.dumps(settings), encoding="utf-8")

    removed = ih._uninstall_claude(config_path)

    assert removed is True
    settings = json.loads(config_path.read_text(encoding="utf-8"))
    assert _all_hook_commands(settings) == ["/usr/bin/python /other/lint.py"]
    assert "protein_design_mode" not in settings
    assert "protein_design_instructions" not in settings


def test_uninstall_claude_handles_legacy_flat_entries(tmp_path):
    """Uninstall also cleans the legacy flat layout, keeping foreign entries."""
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "hooks": [
                    {
                        "event": "UserPromptSubmit",
                        "matcher": "",
                        "command": "python protein_design/hooks/user-onboarding.py",
                        "timeout": 5,
                    },
                    {
                        "event": "UserPromptSubmit",
                        "matcher": "",
                        "command": "python /other/user-hook.py",
                        "timeout": 5,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    removed = ih._uninstall_claude(config_path)

    assert removed is True
    settings = json.loads(config_path.read_text(encoding="utf-8"))
    assert [h["command"] for h in settings["hooks"]] == ["python /other/user-hook.py"]


def test_count_protein_hooks_supports_both_claude_layouts():
    flat = {
        "hooks": [
            {"event": "UserPromptSubmit", "command": "python protein_design/hooks/user-onboarding.py"},
            {"event": "UserPromptSubmit", "command": "python /other/b.py"},
        ]
    }
    nested = {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "matcher": "",
                    "hooks": [
                        {"type": "command", "command": "python protein_design/hooks/user-onboarding.py"},
                        {"type": "command", "command": "python /other/b.py"},
                    ],
                }
            ]
        }
    }
    assert ih._count_protein_hooks(flat) == 1
    assert ih._count_protein_hooks(nested) == 1


def test_load_hooks_source_uses_agent_specific_files():
    assert ih._load_hooks_source(PROJECT_ROOT, "claude")["hooks"]["UserPromptSubmit"][0]["matcher"] == ""
    codex = ih._load_hooks_source(PROJECT_ROOT, "codex")
    assert "matcher" not in codex["hooks"]["UserPromptSubmit"][0]
    assert codex["hooks"]["PreToolUse"][0]["matcher"] == "Bash|PowerShell"
    kimi = ih._load_hooks_source(PROJECT_ROOT, "kimi")
    assert len(list(ih._iter_hook_handlers(kimi))) == 20
    assert all(
        hook["command"].startswith("python ./protein_design/hooks/")
        for _event, _matcher, hook in ih._iter_hook_handlers(
            json.loads((PROJECT_ROOT / "kimi.plugin.json").read_text(encoding="utf-8"))
        )
    )


def test_rewrite_exec_hook_preserves_args_and_special_project_path(tmp_path):
    root = tmp_path / "project & (special)"
    hook_dir = root / "protein_design" / "hooks"
    hook_dir.mkdir(parents=True)
    script = hook_dir / "hook.py"
    script.write_text("# hook\n", encoding="utf-8")
    source = {
        "hooks": [
            {
                "event": "PreToolUse",
                "matcher": "Bash",
                "command": "python",
                "args": ["${CODEX_PLUGIN_ROOT}/protein_design/hooks/hook.py", "--mode", "safe"],
            }
        ]
    }
    rewritten = ih._rewrite_hook_commands(source, root, absolute=False)
    hook = next(ih._iter_hook_handlers(rewritten))[2]
    assert hook["command"] == sys.executable
    assert hook["args"] == [str(script.resolve()), "--mode", "safe"]


def test_which_delegates_to_shutil(monkeypatch):
    monkeypatch.setattr(ih.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    assert ih._which("claude") == "/usr/bin/claude"
    assert ih._which("missing-cmd") is None or isinstance(ih._which("missing-cmd"), str)


def test_install_hooks_returns_false_when_agent_fails(monkeypatch):
    """A swallowed install error must surface as a False return value."""
    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(ih, "_install_claude", boom)
    assert ih.install_hooks(agents=["claude"]) is False


def test_install_hooks_returns_true_on_success(monkeypatch):
    calls = []

    def fake_install(config_path, hooks_config, force=False):
        calls.append(config_path)
        return True

    monkeypatch.setattr(ih, "_install_claude", fake_install)
    assert ih.install_hooks(agents=["claude"]) is True
    assert len(calls) == 1


def test_cli_claude_install_and_force_reinstall_are_idempotent(tmp_path):
    """End-to-end: two --force installs register each of the 20 hooks once."""
    import os

    script = PROJECT_ROOT / "protein_design" / "hooks" / "install-hooks.py"
    env = {**os.environ, "HOME": str(tmp_path)}

    for _ in range(2):
        result = subprocess.run(
            [sys.executable, str(script), "claude", "--force"],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    settings = json.loads(
        (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    commands = _all_hook_commands(settings)
    assert len(commands) == len(set(commands)) == 20
    assert isinstance(settings["hooks"], dict)

    # --list must still report the nested-format install correctly.
    result = subprocess.run(
        [sys.executable, str(script), "--list"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Protein Design hooks registered (20)" in result.stdout


def test_install_codex_omits_empty_matcher(tmp_path):
    config_path = tmp_path / "hooks.json"
    source = {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python protein_design/hooks/user-onboarding.py",
                            "timeout": 5,
                        }
                    ]
                }
            ]
        }
    }

    assert ih._install_codex(config_path, source) is True

    installed = json.loads(config_path.read_text(encoding="utf-8"))
    group = installed["hooks"]["UserPromptSubmit"][0]
    assert "matcher" not in group
    assert len(group["hooks"]) == 1


def test_install_hooks_propagates_uninstall_failure(monkeypatch):
    monkeypatch.setattr(ih, "_uninstall_claude", lambda _path: False)
    assert ih.install_hooks(agents=["claude"], uninstall=True) is False


def test_install_hooks_rejects_unsupported_local_target():
    assert ih.install_hooks(agents=["kimi"], local=True) is False


def test_local_codex_uninstall_does_not_clean_global_legacy_files(
    tmp_path, monkeypatch
):
    local_config = tmp_path / "repo" / ".codex" / "hooks.json"
    local_config.parent.mkdir(parents=True)
    local_config.write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "python protein_design/hooks/user-onboarding.py"
                                    ),
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    legacy_settings = tmp_path / "home" / ".codex" / "settings.json"
    legacy_settings.parent.mkdir(parents=True)
    legacy_text = json.dumps(
        {
            "hooks": {
                "UserPromptSubmit": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": (
                                    "python protein_design/hooks/user-onboarding.py"
                                ),
                            }
                        ]
                    }
                ]
            }
        }
    )
    legacy_settings.write_text(legacy_text, encoding="utf-8")
    legacy_hooks_dir = legacy_settings.parent / "hooks"
    legacy_hooks_dir.mkdir()
    legacy_hook = legacy_hooks_dir / "quality-gate.py"
    legacy_hook.write_text("# legacy managed copy\n", encoding="utf-8")

    monkeypatch.setitem(ih.AGENT_CONFIGS["codex"], "local_config", local_config)
    monkeypatch.setattr(ih, "LEGACY_CODEX_SETTINGS", legacy_settings)
    monkeypatch.setattr(ih, "LEGACY_CODEX_HOOKS_DIR", legacy_hooks_dir)

    assert ih.install_hooks(agents=["codex"], local=True, uninstall=True) is True

    local_settings = json.loads(local_config.read_text(encoding="utf-8"))
    assert local_settings["hooks"] == {}
    assert legacy_settings.read_text(encoding="utf-8") == legacy_text
    assert legacy_hook.exists()

    # Scope is authoritative: even an accidental True flag cannot make a
    # project-local uninstall mutate user-level legacy files.
    assert ih._uninstall_codex(
        local_config, scope="local", cleanup_legacy=True
    ) is False
    assert legacy_settings.read_text(encoding="utf-8") == legacy_text
    assert legacy_hook.exists()


def test_hook_ownership_supports_windows_shell_exec_and_legacy_paths():
    commands = [
        (
            r'"C:\Program Files\Python\python.exe" '
            r'"C:\repo path\protein_design\hooks\quality-gate.py" --mode safe'
        ),
        r"python .\protein_design\hooks\user-onboarding.py",
        {
            "command": r"C:\Python311\python.exe",
            "args": [
                r"${CODEX_PLUGIN_ROOT}\protein_design\hooks\session-health-check.py",
                "{input}",
            ],
        },
        "${PLUGIN_ROOT}/protein_design/hooks/design-report.py",
    ]

    assert all(ih._is_our_hook_command(command) for command in commands)


def test_hook_ownership_rejects_external_commands_and_substring_arguments():
    commands = [
        "echo protein_design/hooks/user-onboarding.py",
        (
            "python /external/tool.py "
            "--note=protein_design/hooks/user-onboarding.py"
        ),
        "python protein_design/hooks/not-managed.py",
        "python -m external protein_design/hooks/user-onboarding.py",
        "/opt/protein_design/hooks-helper.py --version",
        {
            "command": "/usr/bin/external-tool",
            "args": ["protein_design/hooks/user-onboarding.py"],
        },
    ]

    assert not any(ih._is_our_hook_command(command) for command in commands)


def test_windows_shell_join_and_rewrite_use_double_quote_rules(tmp_path):
    tokens = [
        r"C:\Program Files\Python\python.exe",
        r"C:\repo path\protein_design\hooks\quality-gate.py",
        "--label",
        "two words",
    ]
    windows_command = ih._join_shell_tokens(tokens, platform="win32")
    assert windows_command == subprocess.list2cmdline(tokens)
    assert '"C:\\Program Files\\Python\\python.exe"' in windows_command
    assert "'" not in windows_command
    assert ih._join_shell_tokens(["python", "/tmp/a b.py"], platform="linux") == (
        "python '/tmp/a b.py'"
    )

    root = tmp_path / "project with spaces"
    hook_dir = root / "protein_design" / "hooks"
    hook_dir.mkdir(parents=True)
    script = hook_dir / "quality-gate.py"
    script.write_text("# hook\n", encoding="utf-8")
    source = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "command": (
                                'python "${CODEX_PLUGIN_ROOT}/protein_design/'
                                'hooks/quality-gate.py" --label "two words"'
                            )
                        }
                    ],
                }
            ]
        }
    }

    rewritten = ih._rewrite_hook_commands(source, root, platform="win32")
    command = next(ih._iter_hook_handlers(rewritten))[2]["command"]
    assert command == subprocess.list2cmdline(
        [sys.executable, str(script.resolve()), "--label", "two words"]
    )
    assert "'" not in command


def test_install_codex_migrates_legacy_empty_matcher_and_keeps_foreign_hooks(
    tmp_path,
):
    config_path = tmp_path / "hooks.json"
    managed_hook = {
        "type": "command",
        "command": "python protein_design/hooks/user-onboarding.py",
        "timeout": 5,
    }
    foreign_hook = {
        "type": "command",
        "command": "python /other/user-hook.py",
        "timeout": 5,
    }
    config_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "matcher": "",
                            "hooks": [managed_hook, foreign_hook],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    source = {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "hooks": [managed_hook],
                }
            ]
        }
    }

    assert ih._install_codex(config_path, source, force=False) is True

    installed = json.loads(config_path.read_text(encoding="utf-8"))
    groups = installed["hooks"]["UserPromptSubmit"]
    managed_groups = [
        group
        for group in groups
        if any(hook == managed_hook for hook in group["hooks"])
    ]
    assert len(managed_groups) == 1
    assert "matcher" not in managed_groups[0]
    assert any(foreign_hook in group["hooks"] for group in groups)


def test_cli_mixed_valid_and_invalid_agents_exits_nonzero(tmp_path):
    import os

    repo = tmp_path / "repo"
    local_config = repo / ".codex" / "hooks.json"
    local_config.parent.mkdir(parents=True)
    local_config.write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "python protein_design/hooks/user-onboarding.py"
                                    ),
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    home = tmp_path / "home"
    home.mkdir()
    script = PROJECT_ROOT / "protein_design" / "hooks" / "install-hooks.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--local",
            "--uninstall",
            "codex",
            "invalid-agent",
        ],
        cwd=repo,
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Unknown agents" in result.stdout
    assert json.loads(local_config.read_text(encoding="utf-8"))["hooks"] == {}
