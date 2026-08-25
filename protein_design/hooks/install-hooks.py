#!/usr/bin/env python3
"""Cross-agent hook installer for the Protein Design plugin.

Detects installed coding agents and installs hook scripts for each:
  - Claude Code: registers hooks in ~/.claude/settings.json (or .claude/settings.json)
  - Kimi Code: registers hooks in ~/.kimi-code/config.toml
  - Codex CLI: writes hooks to ~/.codex/hooks.json (or .codex/hooks.json)

The single source of truth for hook definitions is hooks/hooks.json.
Project-local installation is supported via --local.

Run this after installing the plugin:

  python install-hooks.py

This installer uses Skills + Hooks + Standalone Scripts only.

Exit codes:
  0 — success (--list finished, --validate passed, or every requested
      install/uninstall completed without error)
  1 — no supported agents detected, no valid agents specified, --validate
      failed, or at least one requested install/uninstall failed
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


PYTHON = sys.executable
HOOKS_SOURCE = "hooks/hooks.json"
PROTEIN_DESIGN_MARKER = "protein-design-hooks"

AGENT_CONFIGS = {
    "claude": {
        "name": "Claude Code",
        "global_config": Path.home() / ".claude" / "settings.json",
        "local_config": Path(".claude") / "settings.json",
        "format": "json",
        "supports_local": True,
    },
    "codex": {
        "name": "Codex CLI",
        "global_config": Path.home() / ".codex" / "hooks.json",
        "local_config": Path(".codex") / "hooks.json",
        "format": "hooks-json",
        "supports_local": True,
    },
    "kimi": {
        "name": "Kimi Code",
        "global_config": Path.home() / ".kimi-code" / "config.toml",
        "local_config": None,
        "format": "toml",
        "supports_local": False,
    },
}

# Legacy paths that we no longer use but should clean up during uninstall.
LEGACY_CODEX_SETTINGS = Path.home() / ".codex" / "settings.json"
LEGACY_CODEX_HOOKS_DIR = Path.home() / ".codex" / "hooks"

HOOK_INSTRUCTIONS = """
# Protein Design Hooks Configuration
#
# This agent is configured with hooks for protein design automation.
# Key principles:
#
# 1. ALWAYS consult skills first (read SKILL_INDEX.md for navigation)
# 2. Let hooks guide execution (they fire automatically on relevant events)
# 3. Use standalone scripts in scripts/ directory for tool execution
# 4. Use direct bash/python commands for all operations
#
# Standalone scripts:
#   scripts/run_pdbfixer.py      — Stage 0: PDB repair
#   scripts/run_rfdiffusion.py   — Stage 1: Backbone generation
#   scripts/run_proteinmpnn.py   — Stage 2: Sequence design
#   scripts/run_alphafold3.py    — Stage 3: Structure validation
#   scripts/run_filtering.py     — Stage 4: Quality filtering
#   scripts/convert_format.py    — Format conversion
#   scripts/batch_runner.py      — Chain all stages
#   scripts/job_manager.py       — Background job management
#
# For pipeline selection: read skill `pipeline-selection`
# For quick start: read skill `quickstart-guide`
"""


# ── Helpers ──────────────────────────────────────────────────────────────


def _escape_toml_string(value: str) -> str:
    r"""Escape a string for TOML basic-string representation.

    TOML basic strings are surrounded by double quotes and support the
    following escape sequences:
      \"  \\  \b  \t  \n  \f  \r  \uXXXX  \UXXXXXXXX
    """
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\b", "\\b")
    value = value.replace("\t", "\\t")
    value = value.replace("\n", "\\n")
    value = value.replace("\f", "\\f")
    value = value.replace("\r", "\\r")
    # Escape remaining control characters (U+0000–U+001F).
    escaped = []
    for ch in value:
        code = ord(ch)
        if code < 0x20:
            escaped.append(f"\\u{code:04x}")
        else:
            escaped.append(ch)
    return "".join(escaped)


def _resolve_hook_script(script_arg: str, project_root: Path) -> Path:
    """Resolve a hook script argument to an absolute path inside the plugin.

    Args:
        script_arg: The script path from the hook command (may contain
                    ${PLUGIN_ROOT}, ${CLAUDE_PLUGIN_ROOT}, or be relative/absolute).
        project_root: Project root directory.

    Returns:
        Absolute, canonical path to the hook script.

    Raises:
        ValueError: If the script path escapes the allowed hooks directory
                    or contains shell metacharacters.
    """
    # Disallow shell metacharacters / command separators in the *declared*
    # path. The plugin-root placeholders are excluded from the screen (they
    # themselves contain "$", "(" and ")"), and the check runs BEFORE
    # substitution so legitimate project roots containing characters like
    # "&" are not falsely rejected.
    checkable = script_arg.replace("${PLUGIN_ROOT}", "").replace("${CLAUDE_PLUGIN_ROOT}", "")
    forbidden = set(";|&$()`\n\r\x00")
    if any(ch in forbidden for ch in checkable):
        raise ValueError(f"Hook script path contains forbidden characters: {script_arg!r}")

    # Resolve plugin-root placeholders first so validation works on literal paths.
    script_arg = script_arg.replace("${PLUGIN_ROOT}", str(project_root))
    script_arg = script_arg.replace("${CLAUDE_PLUGIN_ROOT}", str(project_root))

    script_path = Path(script_arg)
    if not script_path.is_absolute():
        script_path = project_root / script_path

    allowed_dir = (project_root / "protein_design" / "hooks").resolve()
    resolved = script_path.resolve()
    try:
        resolved.relative_to(allowed_dir)
    except ValueError as exc:
        raise ValueError(
            f"Hook script {resolved} is outside allowed directory {allowed_dir}"
        ) from exc
    return resolved


def _load_hooks_source(project_root: Path) -> dict:
    """Load the canonical hooks definition from hooks/hooks.json."""
    source_path = project_root / HOOKS_SOURCE
    if not source_path.exists():
        raise FileNotFoundError(f"Hooks source not found: {source_path}")
    with open(source_path, encoding="utf-8") as f:
        return json.load(f)


def _rewrite_hook_commands(hooks_config: dict, project_root: Path, absolute: bool) -> dict:
    """Rewrite command paths in hooks config.

    Substitutes `${PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_ROOT}` with the actual
    project path and ensures the current Python interpreter (`sys.executable`)
    is used. For global installs this becomes an absolute path; for local
    installs it becomes a relative path (`.` for project-root configs).

    Args:
        hooks_config: Loaded hooks/hooks.json content.
        project_root: Project root directory.
        absolute: If True, use absolute paths to hook scripts.
                  If False, use paths relative to the config file location.

    Raises:
        ValueError: If a hook command points outside the allowed hooks
                    directory or contains shell metacharacters.
    """
    config = json.loads(json.dumps(hooks_config))  # deep copy
    plugin_root = str(project_root) if absolute else "."

    for event_groups in config.get("hooks", {}).values():
        for group in event_groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                if cmd.startswith("python "):
                    script_path = cmd[len("python "):]
                elif cmd.startswith(f"{PYTHON} "):
                    script_path = cmd[len(PYTHON) + 1 :]
                else:
                    continue

                if "${PLUGIN_ROOT}" in script_path:
                    script_path = script_path.replace("${PLUGIN_ROOT}", plugin_root)
                if "${CLAUDE_PLUGIN_ROOT}" in script_path:
                    script_path = script_path.replace("${CLAUDE_PLUGIN_ROOT}", plugin_root)
                elif absolute:
                    script_path = str(project_root / script_path)

                # Validate the resolved path is inside the plugin hooks dir.
                resolved = _resolve_hook_script(script_path, project_root)
                if absolute:
                    hook["command"] = f"{PYTHON} {resolved}"
                else:
                    rel = resolved.relative_to(project_root)
                    hook["command"] = f"{PYTHON} ./{rel.as_posix()}"
    return config


def _which(cmd: str) -> str | None:
    """Return the path to an executable if it exists in PATH."""
    return shutil.which(cmd)


def _detect_agents() -> list[str]:
    """Detect which coding agents are available on this machine.

    Checks for existing config files and for the agent executable in PATH.
    """
    executables = {
        "claude": "claude",
        "codex": "codex",
        "kimi": "kimi",
    }
    available = set()
    for agent_id, cfg in AGENT_CONFIGS.items():
        global_exists = cfg["global_config"].exists()
        local_exists = cfg["local_config"] and cfg["local_config"].exists()
        if global_exists or local_exists:
            available.add(agent_id)
        exe = executables.get(agent_id)
        if exe and _which(exe):
            available.add(agent_id)
    return sorted(available)


# ── Claude Code installer ────────────────────────────────────────────────


def _is_our_hook_command(command: str) -> bool:
    """True if a hook command runs a script from this repo's protein_design/hooks/."""
    return "protein_design/hooks" in command


def _claude_hooks_to_nested(hooks_setting: object) -> dict:
    """Normalize a Claude settings.json 'hooks' value to the nested event layout.

    Claude Code expects each event name to map to a list of matcher groups
    ({"matcher": ..., "hooks": [...]}) — the same layout as hooks/hooks.json.
    Old installer versions wrote a flat list of {"event", "matcher",
    "command", "timeout"} entries instead; those are folded into the nested
    layout here. Event values that cannot be interpreted are preserved
    verbatim so user configuration is never lost.
    """
    nested: dict = {}
    if isinstance(hooks_setting, dict):
        for event, groups in hooks_setting.items():
            if isinstance(groups, list):
                nested[event] = [g for g in groups if isinstance(g, dict)]
            else:
                nested[event] = groups
        return nested
    if isinstance(hooks_setting, list):
        # Legacy flat layout written by old installer versions.
        for entry in hooks_setting:
            if not isinstance(entry, dict) or not entry.get("event"):
                continue
            hook = {"type": "command", "command": entry.get("command", "")}
            if "timeout" in entry:
                hook["timeout"] = entry["timeout"]
            matcher = entry.get("matcher", "")
            for group in nested.setdefault(entry["event"], []):
                if group.get("matcher", "") == matcher:
                    group["hooks"].append(hook)
                    break
            else:
                nested[entry["event"]].append({"matcher": matcher, "hooks": [hook]})
    return nested


def _install_claude(config_path: Path, hooks_config: dict, force: bool = False) -> bool:
    """Install hooks for Claude Code into settings.json.

    Writes Claude Code's nested hook schema (the same layout as
    hooks/hooks.json):

        {"hooks": {"<Event>": [{"matcher": "...",
                                "hooks": [{"type": "command", "command": "...",
                                           "timeout": N}]}]}}

    Existing user hooks (and other settings keys) are preserved. Entries
    previously written by this installer — including flat-list entries from
    old installer versions — are removed first, so repeated installs (with
    or without --force) never duplicate hooks; without --force, an entry
    whose command is still current is kept in place.

    Args:
        config_path: Path to settings.json.
        hooks_config: Canonical hooks configuration (paths already rewritten).
        force: If True, reinstall hooks even if already registered.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    settings = {}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            print(f"  ⚠️  {config_path} is invalid JSON — backing up and recreating")
            shutil.copy2(config_path, config_path.with_suffix(".json.bak"))
            settings = {}

    hooks_by_event = _claude_hooks_to_nested(settings.get("hooks"))

    # Entries this run wants to register.
    desired: list[tuple[str, str, dict]] = []
    for event_name, event_groups in hooks_config.get("hooks", {}).items():
        for group in event_groups:
            matcher = group.get("matcher", "")
            for hook in group.get("hooks", []):
                entry = dict(hook)
                entry.setdefault("type", "command")
                entry.setdefault("timeout", 5)
                desired.append((event_name, matcher, entry))
    desired_commands = {entry["command"] for _, _, entry in desired}

    # Drop hooks this installer wrote previously (any layout, including
    # legacy flat entries converted above) so reinstalls never duplicate.
    # Without --force, an up-to-date entry is kept as-is.
    kept_commands: set = set()
    replaced = 0
    for event_name, groups in list(hooks_by_event.items()):
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            group_hooks = group.get("hooks")
            if not isinstance(group_hooks, list):
                # Not a matcher group we understand — leave untouched.
                kept_groups.append(group)
                continue
            kept_hooks = []
            for hook in group_hooks:
                if not isinstance(hook, dict):
                    kept_hooks.append(hook)
                    continue
                command = hook.get("command", "")
                if not _is_our_hook_command(command):
                    kept_hooks.append(hook)
                elif (
                    not force
                    and command in desired_commands
                    and command not in kept_commands
                ):
                    kept_hooks.append(hook)
                    kept_commands.add(command)
                else:
                    replaced += 1
            if kept_hooks:
                group["hooks"] = kept_hooks
                kept_groups.append(group)
        if kept_groups:
            hooks_by_event[event_name] = kept_groups
        else:
            hooks_by_event.pop(event_name, None)

    if replaced:
        print(f"  ℹ️  Replaced {replaced} previously installed hook entries")

    # Register the desired entries, skipping any that were kept above.
    new_hooks = 0
    for event_name, matcher, entry in desired:
        if entry["command"] in kept_commands:
            print(f"  ⚠️  Hook already registered: {Path(entry['command']).name}")
            continue
        groups = hooks_by_event.get(event_name)
        if not isinstance(groups, list):
            groups = []
            hooks_by_event[event_name] = groups
        for group in groups:
            if group.get("matcher", "") == matcher and isinstance(group.get("hooks"), list):
                group["hooks"].append(entry)
                break
        else:
            groups.append({"matcher": matcher, "hooks": [entry]})
        new_hooks += 1

    if new_hooks:
        print(f"  ✅ Registered {new_hooks} hooks in {config_path}")
    else:
        print("  ℹ️  All hooks already registered.")

    settings["hooks"] = hooks_by_event

    # Set skills+hooks+scripts mode
    settings["protein_design_mode"] = "skills-hooks-scripts"
    settings["protein_design_instructions"] = (
        "Use Skills + Hooks + Direct Execution. "
        "Read SKILL_INDEX.md to find relevant skills. "
        "Use scripts/ directory for standalone execution. "
        "See quickstart-guide skill for getting started."
    )

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    print(f"  ✅ Skills+hooks+scripts mode enabled")
    return True


def _uninstall_claude(config_path: Path) -> bool:
    """Remove Protein Design hooks from Claude Code settings.json.

    Handles both the nested event layout and the legacy flat list written
    by old installer versions, preserving all foreign hooks.
    """
    if not config_path.exists():
        print(f"  ℹ️  No config found at {config_path}")
        return False

    try:
        with open(config_path, encoding="utf-8") as f:
            settings = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"  ⚠️  {config_path} is invalid JSON — cannot uninstall: {exc}")
        return False

    hooks_setting = settings.get("hooks")
    removed = 0
    if isinstance(hooks_setting, list):
        # Legacy flat layout written by old installer versions.
        kept = [
            h for h in hooks_setting
            if not _is_our_hook_command(h.get("command", "") if isinstance(h, dict) else "")
        ]
        removed = len(hooks_setting) - len(kept)
        if kept:
            settings["hooks"] = kept
        else:
            settings.pop("hooks", None)
    elif isinstance(hooks_setting, dict):
        for event_name, groups in list(hooks_setting.items()):
            if not isinstance(groups, list):
                continue
            kept_groups = []
            for group in groups:
                group_hooks = group.get("hooks") if isinstance(group, dict) else None
                if not isinstance(group_hooks, list):
                    kept_groups.append(group)
                    continue
                kept_hooks = [
                    h for h in group_hooks
                    if not _is_our_hook_command(
                        h.get("command", "") if isinstance(h, dict) else ""
                    )
                ]
                removed += len(group_hooks) - len(kept_hooks)
                if kept_hooks:
                    group["hooks"] = kept_hooks
                    kept_groups.append(group)
            if kept_groups:
                hooks_setting[event_name] = kept_groups
            else:
                hooks_setting.pop(event_name, None)

    settings.pop("protein_design_mode", None)
    settings.pop("protein_design_instructions", None)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    if removed:
        print(f"  ✅ Removed {removed} Protein Design hooks from {config_path}")
    else:
        print(f"  ℹ️  No Protein Design hooks found in {config_path}")
    return removed > 0


# ── Codex CLI installer ──────────────────────────────────────────────────


def _is_protein_hook_group(group: dict) -> bool:
    """Return True if a Codex matcher group contains Protein Design hooks."""
    for hook in group.get("hooks", []):
        if "protein_design/hooks" in hook.get("command", ""):
            return True
    return False


def _install_codex(config_path: Path, hooks_config: dict, force: bool = False) -> bool:
    """Install hooks for Codex CLI into hooks.json, merging with existing hooks.

    Args:
        config_path: Path to hooks.json (global or project-local).
        hooks_config: Canonical hooks configuration (paths already rewritten).
        force: If True, remove any existing Protein Design hooks before merging.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    settings: dict = {"hooks": {}}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            print(f"  ⚠️  {config_path} is invalid JSON — backing up and recreating")
            shutil.copy2(config_path, config_path.with_suffix(".json.bak"))
            settings = {"hooks": {}}

    existing_hooks = settings.setdefault("hooks", {})

    if not force:
        # Check if any Protein Design hooks are already present.
        for event_groups in existing_hooks.values():
            for group in event_groups:
                if _is_protein_hook_group(group):
                    print(f"  ⚠️  Codex hooks already installed at {config_path}")
                    print(f"     Use --force to re-merge.")
                    return True

    if force:
        # Remove existing Protein Design matcher groups before merging.
        for event_name, event_groups in list(existing_hooks.items()):
            existing_hooks[event_name] = [
                g for g in event_groups if not _is_protein_hook_group(g)
            ]
            if not existing_hooks[event_name]:
                existing_hooks.pop(event_name, None)

    # Merge in our hooks.
    added = 0
    for event_name, event_groups in hooks_config.get("hooks", {}).items():
        existing_hooks.setdefault(event_name, [])
        for group in event_groups:
            existing_hooks[event_name].append(group)
            added += len(group.get("hooks", []))

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    print(f"  ✅ Installed/merged {added} Codex hooks into {config_path}")
    return True


def _uninstall_codex(config_path: Path) -> bool:
    """Remove Protein Design hooks from Codex hooks.json, preserving other hooks."""
    removed = False
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                settings = json.load(f)
            existing_hooks = settings.get("hooks", {})
            removed_count = 0
            for event_name, event_groups in list(existing_hooks.items()):
                cleaned = [g for g in event_groups if not _is_protein_hook_group(g)]
                removed_count += len(event_groups) - len(cleaned)
                if cleaned:
                    existing_hooks[event_name] = cleaned
                else:
                    existing_hooks.pop(event_name, None)

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)

            if removed_count:
                print(f"  ✅ Removed {removed_count} Protein Design hook groups from {config_path}")
                removed = True
            else:
                print(f"  ℹ️  No Protein Design hooks found in {config_path}")
        except Exception as exc:
            print(f"  ⚠️  Could not read {config_path}: {exc}")
    else:
        print(f"  ℹ️  No hooks file found at {config_path}")

    # Clean up legacy mis-configurations.
    if LEGACY_CODEX_SETTINGS.exists():
        try:
            with open(LEGACY_CODEX_SETTINGS, encoding="utf-8") as f:
                settings = json.load(f)
            original_count = len(settings.get("hooks", []))
            settings["hooks"] = [
                h for h in settings.get("hooks", [])
                if "protein_design/hooks" not in h.get("command", "")
            ]
            if len(settings["hooks"]) < original_count:
                with open(LEGACY_CODEX_SETTINGS, "w", encoding="utf-8") as f:
                    json.dump(settings, f, indent=2)
                print(f"  ✅ Cleaned up legacy hooks from {LEGACY_CODEX_SETTINGS}")
                removed = True
        except Exception as exc:
            print(f"  ⚠️  Could not clean up legacy Codex settings: {exc}")

    if LEGACY_CODEX_HOOKS_DIR.exists():
        managed = _managed_hook_filenames(Path(__file__).resolve().parents[2])
        for f in LEGACY_CODEX_HOOKS_DIR.glob("*.py"):
            if _is_managed_legacy_hook(f, managed):
                f.unlink()
                print(f"  ✅ Removed legacy hook file: {f}")
                removed = True

    return removed


def _managed_hook_filenames(project_root: Path) -> set:
    """Return the basenames of hook scripts the installer manages (from hooks/hooks.json)."""
    names = set()
    try:
        config = _load_hooks_source(project_root)
    except (FileNotFoundError, json.JSONDecodeError):
        return names
    for event_groups in config.get("hooks", {}).values():
        for group in event_groups:
            for hook in group.get("hooks", []):
                for token in hook.get("command", "").split():
                    if token.endswith(".py"):
                        names.add(Path(token).name)
    return names


def _is_managed_legacy_hook(path: Path, managed_names: set) -> bool:
    """True only for files the installer itself placed in the legacy hooks dir.

    A file qualifies when its name matches a canonical hook script from
    hooks/hooks.json, or when its content carries the installer marker block.
    Anything else — including user files that merely contain 'protein' in
    their name — must survive cleanup.
    """
    if path.name in managed_names:
        return True
    try:
        return PROTEIN_DESIGN_MARKER in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


# ── Kimi Code installer ──────────────────────────────────────────────────


def _build_kimi_toml_block(hooks_config: dict) -> str:
    """Build a TOML config block for Kimi Code hooks.

    Values are escaped for TOML basic-string safety.
    """
    lines = [f"# {PROTEIN_DESIGN_MARKER} start"]
    for event_name, event_groups in hooks_config.get("hooks", {}).items():
        for group in event_groups:
            matcher = group.get("matcher", "")
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                timeout = hook.get("timeout", 5)
                lines.append("[[hooks]]")
                lines.append(f'event = "{_escape_toml_string(event_name)}"')
                if matcher:
                    lines.append(f'matcher = "{_escape_toml_string(matcher)}"')
                lines.append(f'command = "{_escape_toml_string(cmd)}"')
                lines.append(f"timeout = {timeout}")
                lines.append("")
    lines.append(f"# {PROTEIN_DESIGN_MARKER} end")
    return "\n".join(lines) + "\n"


def _install_kimi(config_path: Path, hooks_config: dict, force: bool = False) -> bool:
    """Install hooks for Kimi Code into config.toml.

    Args:
        config_path: Path to config.toml.
        hooks_config: Canonical hooks configuration (paths already rewritten).
        force: If True, reinstall hooks even if already registered.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    existing = ""
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            existing = f.read()

    if PROTEIN_DESIGN_MARKER in existing and not force:
        print(f"  ⚠️  Kimi Code config already has Protein Design hooks. Skipping.")
        return True

    # Remove old block and instructions if present (for force reinstall).
    if PROTEIN_DESIGN_MARKER in existing:
        start = existing.find(f"# {PROTEIN_DESIGN_MARKER} start")
        end = existing.find(f"# {PROTEIN_DESIGN_MARKER} end") + len(f"# {PROTEIN_DESIGN_MARKER} end")
        if start >= 0 and end > start:
            existing = existing[:start] + existing[end:]
    if HOOK_INSTRUCTIONS in existing:
        existing = existing.replace(HOOK_INSTRUCTIONS, "")
    existing = existing.rstrip()

    block = _build_kimi_toml_block(hooks_config)

    header = "# Kimi Code configuration\n\n" if not existing else ""
    new_content = f"{existing}\n\n{block}\n{HOOK_INSTRUCTIONS}\n" if existing else f"{header}{block}\n{HOOK_INSTRUCTIONS}\n"
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  ✅ Registered Protein Design hooks in {config_path}")
    return True


def _uninstall_kimi(config_path: Path) -> bool:
    """Remove Protein Design hooks from Kimi Code config.toml."""
    if not config_path.exists():
        print(f"  ℹ️  No config found at {config_path}")
        return False

    with open(config_path, encoding="utf-8") as f:
        content = f.read()

    if PROTEIN_DESIGN_MARKER not in content:
        print(f"  ℹ️  No Protein Design hooks found in {config_path}")
        return False

    start = content.find(f"# {PROTEIN_DESIGN_MARKER} start")
    end = content.find(f"# {PROTEIN_DESIGN_MARKER} end") + len(f"# {PROTEIN_DESIGN_MARKER} end")
    if start < 0 or end <= start:
        print(f"  ⚠️  Could not locate hook block boundaries in {config_path}")
        return False

    new_content = content[:start] + content[end:]
    # Also remove the appended instructions if still present.
    if HOOK_INSTRUCTIONS in new_content:
        new_content = new_content.replace(HOOK_INSTRUCTIONS, "")

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(new_content.strip() + "\n")

    print(f"  ✅ Removed Protein Design hooks from {config_path}")
    return True


# ── Public API ───────────────────────────────────────────────────────────


def install_hooks(
    agents: list[str] | None = None,
    local: bool = False,
    force: bool = False,
    uninstall: bool = False,
) -> bool:
    """Install or uninstall hook scripts for detected or specified coding agents.

    Args:
        agents: List of agent IDs to install for (e.g. ['claude', 'kimi']).
                If None, auto-detects available agents.
        local: If True, install project-local hooks (Claude/Codex only).
        force: If True, reinstall hooks even if already registered.
        uninstall: If True, remove hooks instead of installing.

    Returns:
        True if every requested install/uninstall completed without error,
        False if at least one agent's operation failed.
    """
    source_dir = Path(__file__).parent.resolve()
    project_root = source_dir.parent.parent

    if agents is None:
        agents = _detect_agents()

    if not agents:
        print("No supported coding agents detected on this system.")
        print("\nSupported agents:")
        for agent_id, cfg in AGENT_CONFIGS.items():
            target = cfg["local_config"] if local else cfg["global_config"]
            print(f"  - {cfg['name']} ({target})")
        print("\nInstall an agent first, then re-run this script.")
        print("Or specify agents manually: python install-hooks.py claude kimi")
        sys.exit(1)

    action = "Uninstalling" if uninstall else "Installing"
    print(f"{action} Protein Design hooks for: {', '.join(AGENT_CONFIGS[a]['name'] for a in agents)}\n")
    if not uninstall:
        print("Mode: Skills + Hooks + Standalone Scripts\n")

    all_ok = True
    for agent_id in agents:
        cfg = AGENT_CONFIGS.get(agent_id)
        if not cfg:
            print(f"⚠️  Unknown agent: {agent_id}. Skipping.")
            continue

        if local and not cfg["supports_local"]:
            print(f"⚠️  {cfg['name']} does not support project-local hooks. Skipping.")
            continue

        config_path = cfg["local_config"] if local else cfg["global_config"]

        print(f"── {cfg['name']} ({config_path}) ──")
        try:
            if uninstall:
                if agent_id == "claude":
                    _uninstall_claude(config_path)
                elif agent_id == "codex":
                    _uninstall_codex(config_path)
                elif agent_id == "kimi":
                    _uninstall_kimi(config_path)
                continue

            hooks_config = _load_hooks_source(project_root)
            absolute_paths = not local
            hooks_config = _rewrite_hook_commands(hooks_config, project_root, absolute=absolute_paths)

            if agent_id == "claude":
                _install_claude(config_path, hooks_config, force=force)
            elif agent_id == "codex":
                _install_codex(config_path, hooks_config, force=force)
            elif agent_id == "kimi":
                _install_kimi(config_path, hooks_config, force=force)
        except Exception as exc:
            print(f"  ❌ Failed to {action.lower()} for {cfg['name']}: {exc}")
            all_ok = False
        print()

    if not uninstall:
        print("📝 Next steps:")
        if local:
            print("   1. Project-local hooks are now active for this repository")
            print("   2. Trust the project-local hooks when your agent prompts you")
        else:
            print("   1. Restart your coding agent or start a new session")
        print("   2. Hooks will fire automatically on protein-related prompts")
        print("   3. Read skill 'quickstart-guide' to get started")
        print("   4. Read skill 'pipeline-selection' to choose a design pipeline")
        print("   5. Read skill 'install-guide' to install the tools you need")

    return all_ok


def _count_protein_hooks(data: dict) -> int:
    """Count Protein Design hooks in JSON data.

    Handles the nested event layout (hooks/hooks.json, Codex hooks.json and
    current Claude settings.json) as well as the legacy flat list layout
    written by old installer versions into Claude settings.json.
    """
    hooks = data.get("hooks")
    if isinstance(hooks, list):
        # Legacy flat layout (old Claude settings.json installs).
        return sum(
            1 for h in hooks
            if _is_our_hook_command(h.get("command", "") if isinstance(h, dict) else "")
        )
    if not isinstance(hooks, dict):
        return 0

    count = 0
    for event_groups in hooks.values():
        for group in event_groups:
            for hook in group.get("hooks", []):
                if _is_our_hook_command(hook.get("command", "")):
                    count += 1
    return count


def _validate_claude_plugin_manifest(plugin_data: dict) -> list[str]:
    """Return validation errors for .claude-plugin/plugin.json.

    Marketplace-only fields like `category` and `source` must not appear at
    the top level of the plugin manifest; they belong in marketplace.json.
    """
    errors = []
    if not isinstance(plugin_data, dict):
        return ["plugin.json top-level value is not an object"]

    for key in ("category", "source"):
        if key in plugin_data:
            errors.append(
                f".claude-plugin/plugin.json contains marketplace-only key '{key}'. "
                f"Move it to .claude-plugin/marketplace.json."
            )
    return errors


def _validate_marketplace_manifest(marketplace_data: dict) -> list[str]:
    """Return validation errors for .claude-plugin/marketplace.json.

    Plugin `source` should be a simple string like './' to avoid Claude Code
    copying a nested source object into the cached plugin.json.
    """
    errors = []
    if not isinstance(marketplace_data, dict):
        return ["marketplace.json top-level value is not an object"]

    plugins = marketplace_data.get("plugins", [])
    if not isinstance(plugins, list):
        errors.append("marketplace.json 'plugins' is not an array")
        return errors

    for entry in plugins:
        if not isinstance(entry, dict):
            errors.append("marketplace.json plugins array contains a non-object entry")
            continue

        source = entry.get("source")
        name = entry.get("name", "<unknown>")
        if isinstance(source, dict):
            errors.append(
                f"Marketplace plugin '{name}' uses object-style source {source}. "
                f"Use a simple string source like './'."
            )
        elif source is not None and not isinstance(source, str):
            errors.append(
                f"Marketplace plugin '{name}' source is not a string: {source!r}"
            )
    return errors


def list_hooks() -> None:
    """List hooks registered for each agent."""
    print("Protein Design Hooks — Installation Status\n")

    for agent_id, cfg in AGENT_CONFIGS.items():
        for scope, config_path in [("global", cfg["global_config"]), ("local", cfg["local_config"])]:
            if config_path is None:
                continue
            print(f"── {cfg['name']} ({scope}: {config_path}) ──")

            if not config_path.exists():
                print(f"  ❌ Not installed")
                print()
                continue

            try:
                if cfg["format"] == "toml":
                    with open(config_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if PROTEIN_DESIGN_MARKER in content:
                        print(f"  ✅ Protein Design hooks registered")
                    else:
                        print(f"  ℹ️  Config exists but no Protein Design hooks found")
                elif cfg["format"] == "hooks-json":
                    with open(config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    count = _count_protein_hooks(data)
                    if count:
                        print(f"  ✅ Protein Design hooks registered ({count})")
                    else:
                        print(f"  ℹ️  No Protein Design hooks registered")
                else:
                    with open(config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    count = _count_protein_hooks(data)
                    if count:
                        print(f"  ✅ Protein Design hooks registered ({count})")
                    else:
                        print(f"  ℹ️  No Protein Design hooks registered")
            except Exception as e:
                print(f"  ⚠️  Error reading config: {e}")

            print()


def validate_plugin(project_root: Path) -> bool:
    """Validate plugin manifests and hooks configuration.

    Returns True if all required files are valid, False otherwise.
    """
    print("Validating Protein Design plugin structure\n")
    ok = True

    files_to_check = {
        "Hooks source": project_root / "hooks" / "hooks.json",
        "Root plugin manifest": project_root / "plugin.json",
        "Claude plugin manifest": project_root / ".claude-plugin" / "plugin.json",
        "Codex plugin manifest": project_root / ".codex-plugin" / "plugin.json",
        "Kimi plugin manifest": project_root / "kimi.plugin.json",
        "Claude marketplace": project_root / ".claude-plugin" / "marketplace.json",
        "Codex marketplace": project_root / ".agents" / "plugins" / "marketplace.json",
    }

    for label, path in files_to_check.items():
        print(f"── {label} ({path}) ──")
        if not path.exists():
            print(f"  ❌ File not found")
            ok = False
            print()
            continue

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            if label == "Hooks source":
                if "hooks" not in data:
                    print(f"  ❌ Missing top-level 'hooks' key")
                    ok = False
                else:
                    count = _count_protein_hooks(data)
                    print(f"  ✅ Valid hooks config ({count} hooks)")
                    # Verify referenced scripts exist and are inside allowed dir.
                    missing_scripts = []
                    invalid_scripts = []
                    for event_groups in data["hooks"].values():
                        for group in event_groups:
                            for hook in group.get("hooks", []):
                                cmd = hook.get("command", "")
                                if not cmd.startswith("python ") and not cmd.startswith(f"{PYTHON} "):
                                    invalid_scripts.append(cmd)
                                    continue
                                script = cmd.split(maxsplit=1)[1] if len(cmd.split(maxsplit=1)) > 1 else ""
                                try:
                                    script_path = _resolve_hook_script(script, project_root)
                                    if not script_path.exists():
                                        missing_scripts.append(str(script_path))
                                except ValueError as exc:
                                    invalid_scripts.append(f"{cmd} ({exc})")
                    if invalid_scripts:
                        print(f"  ❌ Invalid hook commands: {invalid_scripts}")
                        ok = False
                    elif missing_scripts:
                        print(f"  ❌ Missing hook scripts: {missing_scripts}")
                        ok = False
                    else:
                        print(f"  ✅ All referenced hook scripts exist and are inside protein_design/hooks")
            elif "plugin" in label.lower() or label == "Kimi plugin manifest":
                if "name" not in data:
                    print(f"  ❌ Missing required 'name' field")
                    ok = False
                else:
                    print(f"  ✅ Valid manifest (name: {data['name']})")
                if label == "Claude plugin manifest":
                    manifest_errors = _validate_claude_plugin_manifest(data)
                    if manifest_errors:
                        for err in manifest_errors:
                            print(f"  ❌ {err}")
                        ok = False
                    else:
                        print("  ✅ Claude plugin manifest has no marketplace-only keys")
            elif label in ("Claude marketplace", "Codex marketplace"):
                if "plugins" not in data:
                    print(f"  ❌ Missing 'plugins' array")
                    ok = False
                else:
                    print(f"  ✅ Valid marketplace ({len(data['plugins'])} plugin(s))")
                if label == "Claude marketplace":
                    marketplace_errors = _validate_marketplace_manifest(data)
                    if marketplace_errors:
                        for err in marketplace_errors:
                            print(f"  ❌ {err}")
                        ok = False
                    else:
                        print("  ✅ Marketplace plugin entries use string sources")
        except json.JSONDecodeError as exc:
            print(f"  ❌ Invalid JSON: {exc}")
            ok = False
        except Exception as exc:
            print(f"  ⚠️  Error validating: {exc}")
            ok = False
        print()

    if ok:
        print("✅ All plugin files are valid")
    else:
        print("❌ Some plugin files are missing or invalid")
    return ok


# ── CLI ──────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Install Protein Design hooks for coding agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect agents and install hooks globally
  python install-hooks.py

  # Install for specific agents
  python install-hooks.py claude kimi

  # Install for all supported agents
  python install-hooks.py claude kimi codex

  # Install project-local hooks (Claude/Codex only)
  python install-hooks.py --local claude codex

  # Force reinstall
  python install-hooks.py claude --force

  # Uninstall hooks
  python install-hooks.py --uninstall claude codex

  # List installed hooks
  python install-hooks.py --list

  # Validate plugin manifests
  python install-hooks.py --validate
        """
    )
    parser.add_argument(
        "agents",
        nargs="*",
        help="Agent IDs to install for (claude, kimi, codex). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List installed hooks for each agent and exit.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Install project-local hooks instead of global user hooks.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reinstall hooks even if already registered.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove Protein Design hooks for the specified agents.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate plugin manifests and hooks configuration.",
    )
    args = parser.parse_args()

    if args.list:
        list_hooks()
        sys.exit(0)

    source_dir = Path(__file__).parent.resolve()
    project_root = source_dir.parent.parent

    if args.validate:
        ok = validate_plugin(project_root)
        sys.exit(0 if ok else 1)

    # Filter valid agents from positional args
    agents = None
    if args.agents:
        agents = [a for a in args.agents if a in AGENT_CONFIGS]
        invalid = [a for a in args.agents if a not in AGENT_CONFIGS]
        if invalid:
            print(f"⚠️  Unknown agents (ignored): {invalid}")
        if not agents:
            print(f"No valid agents specified. Valid: {list(AGENT_CONFIGS.keys())}")
            sys.exit(1)

    ok = install_hooks(agents=agents, local=args.local, force=args.force, uninstall=args.uninstall)
    sys.exit(0 if ok else 1)
