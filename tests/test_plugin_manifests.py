"""Regression tests for plugin manifest structure.

Validates .claude-plugin/plugin.json, .claude-plugin/marketplace.json,
and .codex-plugin/plugin.json against the approved manifest cleanup conventions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from tests.helpers import load_install_hooks_module as _load_install_hooks_module

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


_INSTALL_HOOKS = _load_install_hooks_module()

_CLAUDE_PLUGIN_JSON = json.loads(
    (_PROJECT_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
)
_CLAUDE_MARKETPLACE_JSON = json.loads(
    (_PROJECT_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
)
_CODEX_PLUGIN_JSON = json.loads(
    (_PROJECT_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
)


def test_claude_plugin_json_has_required_fields():
    assert _CLAUDE_PLUGIN_JSON["name"] == "protein-design-skills"
    assert _CLAUDE_PLUGIN_JSON["author"]["name"] == "DevXia"
    assert "homepage" in _CLAUDE_PLUGIN_JSON, "homepage field is required"
    assert _CLAUDE_PLUGIN_JSON.get("skills") == "./skills/"
    # Claude Code auto-discovers hooks/hooks.json by convention; declaring the
    # default path in the manifest causes a duplicate-load error.
    assert "hooks" not in _CLAUDE_PLUGIN_JSON, (
        "Claude manifest should not declare the default hooks/hooks.json path"
    )


def test_claude_plugin_json_has_no_marketplace_only_keys():
    forbidden = {"category", "source"}
    found = forbidden & set(_CLAUDE_PLUGIN_JSON.keys())
    assert not found, f"plugin.json contains marketplace-only keys: {found}"


def test_claude_marketplace_source_is_string():
    plugins = _CLAUDE_MARKETPLACE_JSON.get("plugins")
    assert isinstance(plugins, list), (
        f"expected marketplace 'plugins' to be a list, got {type(plugins).__name__}"
    )
    for entry in plugins:
        source = entry.get("source")
        assert isinstance(source, str), (
            f"marketplace plugin {entry.get('name')!r} has non-string source: {source!r}"
        )
        assert source == "./", (
            f"marketplace plugin {entry.get('name')!r} source should be './', got {source!r}"
        )


def test_claude_marketplace_has_category():
    plugins = _CLAUDE_MARKETPLACE_JSON.get("plugins")
    assert isinstance(plugins, list), (
        f"expected marketplace 'plugins' to be a list, got {type(plugins).__name__}"
    )
    for entry in plugins:
        assert "category" in entry, f"marketplace plugin {entry.get('name')!r} missing category"


def test_codex_plugin_json_interface_complete():
    interface = _CODEX_PLUGIN_JSON.get("interface", {})
    required = {
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
        "websiteURL",
        "privacyPolicyURL",
        "termsOfServiceURL",
        "brandColor",
    }
    missing = required - set(interface.keys())
    assert not missing, f"Codex interface missing fields: {missing}"
    assert _CODEX_PLUGIN_JSON["author"]["name"] == "DevXia"
    assert _CODEX_PLUGIN_JSON["author"]["url"] == "https://github.com/devxia"


def test_validate_claude_plugin_rejects_forbidden_keys():
    validate = _INSTALL_HOOKS._validate_claude_plugin_manifest

    bad = {"name": "x", "category": "science"}
    errors = validate(bad)
    assert any("category" in e for e in errors), (
        f"expected validation errors mentioning 'category' for {bad!r}, got {errors!r}"
    )

    bad2 = {"name": "x", "source": {"source": "url"}}
    errors = validate(bad2)
    assert any("source" in e for e in errors), (
        f"expected validation errors mentioning 'source' for {bad2!r}, got {errors!r}"
    )

    good = {"name": "x", "skills": "./skills/"}
    assert validate(good) == [], (
        f"expected no validation errors for valid plugin {good!r}, got {validate(good)!r}"
    )


def test_rewrite_hook_commands_substitutes_both_root_placeholders():
    """hooks.json may use ${PLUGIN_ROOT} or ${CLAUDE_PLUGIN_ROOT}; both must be replaced."""
    rewrite = _INSTALL_HOOKS._rewrite_hook_commands
    source = {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python ${CLAUDE_PLUGIN_ROOT}/protein_design/hooks/user-onboarding.py",
                        }
                    ]
                }
            ]
        }
    }
    rewritten = rewrite(source, _PROJECT_ROOT, absolute=True)
    cmd = rewritten["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert "${PLUGIN_ROOT}" not in cmd
    assert "${CLAUDE_PLUGIN_ROOT}" not in cmd
    assert cmd.startswith(sys.executable)
    assert cmd.endswith("protein_design/hooks/user-onboarding.py")


def test_validate_marketplace_rejects_object_source():
    validate = _INSTALL_HOOKS._validate_marketplace_manifest

    bad = {
        "plugins": [
            {"name": "x", "source": {"source": "git-subdir", "url": "...", "path": "."}}
        ]
    }
    errors = validate(bad)
    assert errors, f"expected validation errors for object source {bad!r}, got {errors!r}"

    good = {"plugins": [{"name": "x", "source": "./"}]}
    assert validate(good) == [], (
        f"expected no validation errors for valid marketplace {good!r}, got {validate(good)!r}"
    )


def test_rewrite_hook_commands_local_uses_relative_paths():
    rewrite = _INSTALL_HOOKS._rewrite_hook_commands
    source = {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python ${CLAUDE_PLUGIN_ROOT}/protein_design/hooks/user-onboarding.py",
                        }
                    ]
                }
            ]
        }
    }
    rewritten = rewrite(source, _PROJECT_ROOT, absolute=False)
    cmd = rewritten["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    parts = cmd.split(maxsplit=1)
    assert parts[0] == sys.executable
    assert parts[1].startswith("./protein_design/hooks/")
    assert not Path(parts[1]).is_absolute()
    assert "${PLUGIN_ROOT}" not in cmd
    assert "${CLAUDE_PLUGIN_ROOT}" not in cmd


def test_all_manifests_use_canonical_author():
    plugin = json.loads((_PROJECT_ROOT / "plugin.json").read_text(encoding="utf-8"))
    kimi = json.loads((_PROJECT_ROOT / "kimi.plugin.json").read_text(encoding="utf-8"))
    agents = json.loads((_PROJECT_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))

    assert plugin["author"]["name"] == "DevXia"
    assert kimi["author"]["name"] == "DevXia"
    assert kimi["interface"]["developerName"] == "DevXia"
    assert agents["owner"]["name"] == "DevXia"
    for entry in agents["plugins"]:
        assert entry["author"]["name"] == "DevXia"


def test_hook_matchers_do_not_overmatch():
    hooks = json.loads((_PROJECT_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    for event_groups in hooks["hooks"].values():
        for group in event_groups:
            matcher = group.get("matcher", "")
            assert "run_chai1?" not in matcher
            assert "run_alphafold3?" not in matcher
            assert "run_openfold3?" not in matcher
