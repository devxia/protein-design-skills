#!/usr/bin/env python3
"""Cross-agent hook installer for the Protein Design plugin.

Detects installed coding agents and installs hook scripts for each:
  - Claude Code: registers hooks in ~/.claude/settings.json (or .claude/settings.json)
  - Kimi Code: registers hooks in ~/.kimi-code/config.toml
  - Codex CLI: writes hooks to ~/.codex/hooks.json (or .codex/hooks.json)

Hook definitions are stored in host-specific sources:
  - Claude Code: hooks/hooks.json
  - Codex CLI: hooks/codex-hooks.json
  - Kimi Code: kimi.plugin.json
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
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple


PYTHON = sys.executable
HOOKS_SOURCE = "hooks/hooks.json"
HOOKS_SOURCES = {
    "claude": "hooks/hooks.json",
    "codex": "hooks/codex-hooks.json",
    "kimi": "kimi.plugin.json",
}
PROTEIN_DESIGN_MARKER = "protein-design-hooks"
_MANAGED_HOOK_FILENAMES = None
HOOK_ROOT_PLACEHOLDERS = (
    "${PLUGIN_ROOT}",
    "${CLAUDE_PLUGIN_ROOT}",
    "${CODEX_PLUGIN_ROOT}",
    "${KIMI_PLUGIN_ROOT}",
)

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
    """Resolve a declared hook script to an absolute path inside the plugin."""
    checkable = script_arg
    for placeholder in HOOK_ROOT_PLACEHOLDERS:
        checkable = checkable.replace(placeholder, "")
    forbidden = set(";|&$()`\n\r\x00")
    if any(ch in forbidden for ch in checkable):
        raise ValueError(f"Hook script path contains forbidden characters: {script_arg!r}")

    for placeholder in HOOK_ROOT_PLACEHOLDERS:
        script_arg = script_arg.replace(placeholder, str(project_root))

    # Windows-native manifest commands use backslashes even when validation is
    # running on POSIX. Normalizing here keeps the containment check identical.
    script_path = Path(script_arg.replace("\\", "/"))
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


def _normalise_flat_hooks(hooks: object) -> dict:
    """Convert flat ``event`` hook entries to the nested host schema."""
    if isinstance(hooks, dict):
        return {"hooks": hooks}

    nested: dict = {}
    if isinstance(hooks, list):
        for entry in hooks:
            if not isinstance(entry, dict) or not entry.get("event"):
                continue
            event = str(entry["event"])
            matcher = str(entry.get("matcher") or "")
            groups = nested.setdefault(event, [])
            group = next(
                (g for g in groups if g.get("matcher", "") == matcher),
                None,
            )
            if group is None:
                group = {"hooks": []}
                if matcher:
                    group["matcher"] = matcher
                groups.append(group)
            handler = {
                key: value
                for key, value in entry.items()
                if key not in {"event", "matcher"}
            }
            group["hooks"].append(handler)
    return {"hooks": nested}


def _normalise_hook_config(config: object) -> dict:
    """Return any supported hook layout as ``{"hooks": ...}``."""
    if isinstance(config, list):
        return _normalise_flat_hooks(config)
    if isinstance(config, dict):
        hooks = config.get("hooks", config)
        return _normalise_flat_hooks(hooks)
    return {"hooks": {}}


def _load_hooks_source(project_root: Path, agent_id: str = "claude") -> dict:
    """Load the hook definition for one host and normalise its layout."""
    source_rel = HOOKS_SOURCES.get(agent_id)
    if source_rel is None:
        raise ValueError(f"Unsupported hook host: {agent_id}")
    source_path = project_root / source_rel
    if not source_path.exists():
        raise FileNotFoundError(f"Hooks source not found: {source_path}")
    with open(source_path, encoding="utf-8") as f:
        data = json.load(f)
    return _normalise_hook_config(data)


def _iter_hook_handlers(hooks_config: object):
    """Yield ``(event, matcher, handler)`` triples from either hook layout."""
    if isinstance(hooks_config, list):
        hooks = hooks_config
    elif isinstance(hooks_config, dict):
        hooks = hooks_config.get("hooks")
    else:
        hooks = None

    if isinstance(hooks, list):
        for entry in hooks:
            if isinstance(entry, dict) and entry.get("event"):
                yield str(entry["event"]), str(entry.get("matcher") or ""), entry
        return
    if not isinstance(hooks, dict):
        return

    for event_name, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = str(group.get("matcher") or "")
            handlers = group.get("hooks", [])
            if not isinstance(handlers, list):
                continue
            for handler in handlers:
                if isinstance(handler, dict):
                    yield str(event_name), matcher, handler


def _is_windows_platform(platform: Optional[str] = None) -> bool:
    """Return whether shell command handling should use Windows semantics."""
    return (platform or sys.platform).lower().startswith("win")


def _strip_shell_quotes(token: str) -> str:
    """Strip one matching pair of shell quotes from a parsed token."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        return token[1:-1]
    return token


def _split_shell_tokens(command: str, platform: Optional[str] = None) -> List[str]:
    """Split a command using the quoting rules for the requested platform."""
    windows = _is_windows_platform(platform)
    tokens = shlex.split(command, posix=not windows)
    if windows:
        tokens = [_strip_shell_quotes(token) for token in tokens]
    return tokens


def _hook_command_value(hook: dict, platform: Optional[str] = None) -> str:
    """Return the host-native command field for the requested platform."""
    field = "commandWindows" if _is_windows_platform(platform) else "command"
    command = hook.get(field, hook.get("command", ""))
    return command if isinstance(command, str) else ""


def _hook_script_argument(
    hook: dict, platform: Optional[str] = None
) -> Optional[Tuple[str, int]]:
    """Return the script-bearing field and index for shell or exec hooks."""
    args = hook.get("args")
    if isinstance(args, list):
        for index, value in enumerate(args):
            if isinstance(value, str) and value.endswith(".py"):
                return "args", index

    command = _hook_command_value(hook, platform=platform)
    if not command:
        return None
    try:
        tokens = _split_shell_tokens(command, platform=platform)
    except ValueError:
        tokens = command.split()
    for index, token in enumerate(tokens):
        if token.endswith(".py"):
            return "command", index
    return None


def _quote_shell_token(token: str) -> str:
    """Quote shell-unsafe tokens without quoting ordinary executable paths."""
    unsafe = set("'\\\"$`;&|()<>*?![]{}~#^\n\r\x00")
    if token and not any(ch.isspace() or ch in unsafe for ch in token):
        return token
    return shlex.quote(token)


def _quote_windows_shell_token(token: str) -> str:
    """Quote a token for cmd-compatible Windows hook commands.

    ``list2cmdline`` handles argv quoting but leaves shell operators unquoted
    when a path has no whitespace.  Those characters would be interpreted by
    cmd.exe, so force a quoted token for them and reject expansion characters
    that cannot be made safe in a generated command string.
    """
    if any(char in token for char in ("%", "!", "\n", "\r", "\x00")):
        raise ValueError("Windows hook command token contains unsafe expansion characters")
    rendered = subprocess.list2cmdline([token])
    if any(char in token for char in "&|<>()^") and not rendered.startswith('"'):
        return f'"{rendered}"'
    return rendered


def _join_shell_tokens(
    tokens: List[str], platform: Optional[str] = None
) -> str:
    """Join shell tokens using the requested platform's quoting rules."""
    if _is_windows_platform(platform):
        return " ".join(_quote_windows_shell_token(token) for token in tokens)
    return " ".join(_quote_shell_token(token) for token in tokens)


def _rewrite_hook_commands(
    hooks_config: dict,
    project_root: Path,
    absolute: bool = True,
    platform: Optional[str] = None,
) -> dict:
    """Rewrite hook script paths for an installed configuration.

    Both legacy shell commands and ``command`` + ``args`` hooks are accepted.
    Installed configurations always contain absolute script paths, including
    project-local installations, because hosts may invoke a hook with a
    different current working directory.
    """
    del absolute  # Kept in the public helper signature for compatibility.
    config = json.loads(json.dumps(hooks_config))

    for _event, _matcher, hook in _iter_hook_handlers(config):
        location = _hook_script_argument(hook, platform=platform)
        if location is None:
            continue
        field, index = location
        if field == "args":
            script_arg = hook["args"][index]
            resolved = _resolve_hook_script(script_arg, project_root)
            hook["command"] = PYTHON
            hook["args"][index] = str(resolved)
            continue

        command = _hook_command_value(hook, platform=platform)
        try:
            tokens = _split_shell_tokens(command, platform=platform)
        except ValueError as exc:
            raise ValueError(f"Invalid hook command: {command!r}") from exc
        if index >= len(tokens):
            continue
        resolved = _resolve_hook_script(tokens[index], project_root)
        if index == 0:
            tokens = [PYTHON, str(resolved)] + tokens[1:]
        else:
            tokens[0] = PYTHON
            tokens[index] = str(resolved)
        # Installed fallback configurations contain an absolute command for the
        # active host, not the plugin manifest's root-relative variant.
        hook["command"] = _join_shell_tokens(tokens, platform=platform)
        hook.pop("commandWindows", None)
    return config


def _hook_command_text(hook: object) -> str:
    """Return a searchable representation of a shell or exec hook."""
    if isinstance(hook, str):
        return hook
    if not isinstance(hook, dict):
        return ""
    command = hook.get("command", "")
    args = hook.get("args", [])
    parts = [str(command)] if command else []
    if isinstance(args, list):
        parts.extend(str(value) for value in args)
    return " ".join(parts)


def _hook_identity(hook: object) -> str:
    """Return a stable identity for shell and exec hook deduplication."""
    if isinstance(hook, dict):
        return json.dumps(
            {"command": hook.get("command", ""), "args": hook.get("args", [])},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    return _hook_command_text(hook)


def _which(cmd: str) -> Optional[str]:
    """Return the path to an executable if it exists in PATH."""
    return shutil.which(cmd)


def _detect_agents() -> List[str]:
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


def _is_python_executable(token: str) -> bool:
    """Return True for the common Python launcher/interpreter names."""
    name = _strip_shell_quotes(token).replace("\\", "/").rsplit("/", 1)[-1]
    return re.fullmatch(
        r"(?:pythonw?|py)(?:\d+(?:\.\d+)*)?(?:\.exe)?",
        name,
        flags=re.IGNORECASE,
    ) is not None


def _actual_python_script(tokens: List[str]) -> Optional[str]:
    """Return the script executed by a direct script or Python command."""
    if not tokens:
        return None

    first = _strip_shell_quotes(tokens[0])
    if first.lower().endswith(".py") and not first.startswith("-"):
        return first

    interpreter_index = 0
    first_name = first.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if first_name in {"env", "env.exe"}:
        interpreter_index = next(
            (
                index
                for index, token in enumerate(tokens[1:], start=1)
                if _is_python_executable(token)
            ),
            -1,
        )
    elif not _is_python_executable(first):
        return None

    if interpreter_index < 0:
        return None

    arguments = tokens[interpreter_index + 1 :]
    index = 0
    while index < len(arguments):
        candidate = _strip_shell_quotes(arguments[index])
        if candidate in {"-c", "-m"}:
            # These modes execute code or a module; later .py values are only
            # arguments to that external command, not the executed script.
            return None
        if candidate in {"-W", "-X", "--check-hash-based-pycs"}:
            index += 2
            continue
        if candidate == "--":
            index += 1
            if index >= len(arguments):
                return None
            candidate = _strip_shell_quotes(arguments[index])
        elif candidate.startswith("-"):
            index += 1
            continue
        return candidate if candidate.lower().endswith(".py") else None
    return None


def _normalised_path_components(path: str) -> List[str]:
    """Normalize slash styles and dot segments without touching the filesystem."""
    components = []
    for component in _strip_shell_quotes(path).replace("\\", "/").split("/"):
        if not component or component == ".":
            continue
        if component == ".." and components and components[-1] != "..":
            components.pop()
        else:
            components.append(component)
    return components


def _managed_hook_names() -> set:
    """Return the cached set of hook basenames declared by this project."""
    global _MANAGED_HOOK_FILENAMES
    if _MANAGED_HOOK_FILENAMES is None:
        project_root = Path(__file__).resolve().parents[2]
        _MANAGED_HOOK_FILENAMES = _managed_hook_filenames(project_root)
    return _MANAGED_HOOK_FILENAMES


def _is_managed_script_path(path: str) -> bool:
    """Match an exact managed script path under protein_design/hooks."""
    if path.startswith("-"):
        return False
    components = _normalised_path_components(path)
    if len(components) < 3:
        return False

    windows_path = "\\" in path or bool(re.match(r"^[A-Za-z]:", path))
    if windows_path:
        tail = [component.casefold() for component in components[-3:]]
        managed_names = {name.casefold() for name in _managed_hook_names()}
    else:
        tail = components[-3:]
        managed_names = _managed_hook_names()
    return tail[:2] == ["protein_design", "hooks"] and tail[2] in managed_names


def _is_our_hook_command(command: object) -> bool:
    """Return True only when the command executes one of our managed scripts."""
    if isinstance(command, str):
        command_text = command
        args: List[str] = []
    elif isinstance(command, dict):
        raw_command = command.get("command", "")
        if not isinstance(raw_command, str):
            return False
        command_text = raw_command
        raw_args = command.get("args", [])
        args = [str(value) for value in raw_args] if isinstance(raw_args, list) else []
    else:
        return False

    # Parse both command syntaxes when backslashes are present. This makes
    # ownership checks deterministic even when inspecting Windows config on
    # a POSIX machine, while retaining POSIX backslash escaping support.
    platforms = ("linux", "win32") if "\\" in command_text else ("linux",)
    for platform in platforms:
        try:
            tokens = _split_shell_tokens(command_text, platform=platform)
        except ValueError:
            continue
        script = _actual_python_script(tokens + args)
        if script is not None and _is_managed_script_path(script):
            return True
    return False


def _claude_hooks_to_nested(hooks_setting: object) -> dict:
    """Normalize nested and legacy flat settings without dropping user hooks."""
    return _normalise_hook_config({"hooks": hooks_setting}).get("hooks", {})


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
    desired: List[Tuple[str, str, dict]] = []
    for event_name, matcher, hook in _iter_hook_handlers(hooks_config):
        entry = dict(hook)
        entry.setdefault("type", "command")
        entry.setdefault("timeout", 5)
        desired.append((event_name, matcher, entry))
    desired_keys = {
        (event_name, matcher, _hook_identity(entry))
        for event_name, matcher, entry in desired
    }

    # Drop hooks this installer wrote previously (any layout, including
    # legacy flat entries converted above) so reinstalls never duplicate.
    # Without --force, an up-to-date entry is kept as-is.
    kept_keys = set()
    replaced = 0
    for event_name, groups in list(hooks_by_event.items()):
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue
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
                if not _is_our_hook_command(hook):
                    kept_hooks.append(hook)
                    continue
                hook_id = _hook_identity(hook)
                hook_key = (event_name, str(group.get("matcher") or ""), hook_id)
                if not force and hook_key in desired_keys and hook_key not in kept_keys:
                    kept_hooks.append(hook)
                    kept_keys.add(hook_key)
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
        if (event_name, matcher, _hook_identity(entry)) in kept_keys:
            print(f"  ⚠️  Hook already registered: {Path(str(entry.get('command', ''))).name}")
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
        kept_keys.add((event_name, matcher, _hook_identity(entry)))
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
        kept = [h for h in hooks_setting if not _is_our_hook_command(h)]
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
                kept_hooks = [h for h in group_hooks if not _is_our_hook_command(h)]
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


def _is_protein_hook_group(group: object) -> bool:
    """Return True if a Codex matcher group contains a Protein Design hook."""
    if not isinstance(group, dict):
        return False
    return any(_is_our_hook_command(hook) for hook in group.get("hooks", []))


def _install_codex(config_path: Path, hooks_config: dict, force: bool = False) -> bool:
    """Install Codex hooks as nested JSON while preserving user hooks."""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    settings: dict = {"hooks": {}}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                loaded = json.load(f)
            settings = loaded if isinstance(loaded, dict) else {"hooks": {}}
        except json.JSONDecodeError:
            print(f"  ⚠️  {config_path} is invalid JSON — backing up and recreating")
            shutil.copy2(config_path, config_path.with_suffix(".json.bak"))
            settings = {"hooks": {}}

    existing_config = _normalise_hook_config(settings.get("hooks", {}))
    existing_hooks = existing_config.get("hooks", {})
    desired_config = _normalise_hook_config(hooks_config)
    desired = [
        (event_name, matcher, dict(hook))
        for event_name, matcher, hook in _iter_hook_handlers(desired_config)
    ]
    desired_keys = {
        (event_name, matcher, _hook_identity(hook))
        for event_name, matcher, hook in desired
    }

    # Remove stale/duplicate hooks previously managed by this installer, but
    # retain foreign hooks even when they share a matcher group with ours.
    kept_keys = set()
    replaced = 0
    for event_name, groups in list(existing_hooks.items()):
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                kept_groups.append(group)
                continue
            kept_handlers = []
            legacy_empty_matcher = "matcher" in group and group.get("matcher") == ""
            for hook in handlers:
                if not isinstance(hook, dict) or not _is_our_hook_command(hook):
                    kept_handlers.append(hook)
                    continue
                hook_id = _hook_identity(hook)
                hook_key = (event_name, str(group.get("matcher") or ""), hook_id)
                if (
                    not force
                    and not legacy_empty_matcher
                    and hook_key in desired_keys
                    and hook_key not in kept_keys
                ):
                    kept_handlers.append(hook)
                    kept_keys.add(hook_key)
                else:
                    replaced += 1
            if kept_handlers:
                group["hooks"] = kept_handlers
                kept_groups.append(group)
        if kept_groups:
            existing_hooks[event_name] = kept_groups
        else:
            existing_hooks.pop(event_name, None)

    if replaced:
        print(f"  ℹ️  Replaced {replaced} previously installed Codex hook entries")

    added = 0
    for event_name, matcher, hook in desired:
        hook_id = _hook_identity(hook)
        hook_key = (event_name, matcher, hook_id)
        if hook_key in kept_keys:
            continue
        groups = existing_hooks.get(event_name)
        if not isinstance(groups, list):
            groups = []
            existing_hooks[event_name] = groups
        for group in groups:
            if (
                isinstance(group, dict)
                and group.get("matcher", "") == matcher
                and (bool(matcher) or "matcher" not in group)
                and isinstance(group.get("hooks"), list)
            ):
                group["hooks"].append(hook)
                break
        else:
            group = {"hooks": [hook]}
            # Codex treats an omitted matcher as "all". An explicit empty
            # matcher is not part of its documented hook schema.
            if matcher:
                group["matcher"] = matcher
            groups.append(group)
        kept_keys.add(hook_key)
        added += 1

    settings["hooks"] = existing_hooks
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    print(f"  ✅ Installed/merged {added} Codex hooks into {config_path}")
    return True


def _uninstall_codex(
    config_path: Path,
    scope: str = "global",
    cleanup_legacy: Optional[bool] = None,
) -> bool:
    """Remove Codex hooks, cleaning user-level legacy files only globally.

    Direct callers retain the historical global-cleanup behavior. Passing a
    local scope always disables legacy cleanup, even if cleanup_legacy is True.
    """
    if scope not in {"global", "local"}:
        raise ValueError(f"Unsupported Codex uninstall scope: {scope}")
    if cleanup_legacy is None:
        cleanup_legacy = scope == "global"
    cleanup_legacy = bool(cleanup_legacy and scope == "global")

    removed = False
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                settings = json.load(f)
            if not isinstance(settings, dict):
                settings = {"hooks": {}}
            existing_config = _normalise_hook_config(settings.get("hooks", {}))
            existing_hooks = existing_config.get("hooks", {})
            removed_count = 0
            for event_name, event_groups in list(existing_hooks.items()):
                if not isinstance(event_groups, list):
                    continue
                kept_groups = []
                for group in event_groups:
                    if not isinstance(group, dict):
                        kept_groups.append(group)
                        continue
                    handlers = group.get("hooks")
                    if not isinstance(handlers, list):
                        kept_groups.append(group)
                        continue
                    kept_handlers = [
                        hook for hook in handlers
                        if not _is_our_hook_command(hook)
                    ]
                    removed_count += len(handlers) - len(kept_handlers)
                    if kept_handlers:
                        group["hooks"] = kept_handlers
                        kept_groups.append(group)
                if kept_groups:
                    existing_hooks[event_name] = kept_groups
                else:
                    existing_hooks.pop(event_name, None)
            settings["hooks"] = existing_hooks

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)

            if removed_count:
                print(f"  ✅ Removed {removed_count} Protein Design hooks from {config_path}")
                removed = True
            else:
                print(f"  ℹ️  No Protein Design hooks found in {config_path}")
        except Exception as exc:
            print(f"  ⚠️  Could not read {config_path}: {exc}")
    else:
        print(f"  ℹ️  No hooks file found at {config_path}")

    # Clean up legacy user-level mis-configurations for global uninstalls only.
    if cleanup_legacy and LEGACY_CODEX_SETTINGS.exists():
        try:
            with open(LEGACY_CODEX_SETTINGS, encoding="utf-8") as f:
                settings = json.load(f)
            original_hooks = settings.get("hooks", {})
            normalized = _normalise_hook_config({"hooks": original_hooks})
            cleaned_config = _normalise_hook_config(normalized)
            removed_count = 0
            cleaned_hooks = {}
            for event_name, groups in cleaned_config.get("hooks", {}).items():
                if not isinstance(groups, list):
                    cleaned_hooks[event_name] = groups
                    continue
                kept_groups = []
                for group in groups:
                    if not isinstance(group, dict):
                        kept_groups.append(group)
                        continue
                    handlers = group.get("hooks", [])
                    if not isinstance(handlers, list):
                        kept_groups.append(group)
                        continue
                    kept_handlers = [h for h in handlers if not _is_our_hook_command(h)]
                    removed_count += len(handlers) - len(kept_handlers)
                    if kept_handlers:
                        group["hooks"] = kept_handlers
                        kept_groups.append(group)
                if kept_groups:
                    cleaned_hooks[event_name] = kept_groups
            settings["hooks"] = cleaned_hooks
            if removed_count:
                with open(LEGACY_CODEX_SETTINGS, "w", encoding="utf-8") as f:
                    json.dump(settings, f, indent=2)
                print(f"  ✅ Cleaned up legacy hooks from {LEGACY_CODEX_SETTINGS}")
                removed = True
        except Exception as exc:
            print(f"  ⚠️  Could not clean up legacy Codex settings: {exc}")

    if cleanup_legacy and LEGACY_CODEX_HOOKS_DIR.exists():
        managed = _managed_hook_filenames(Path(__file__).resolve().parents[2])
        for f in LEGACY_CODEX_HOOKS_DIR.glob("*.py"):
            if _is_managed_legacy_hook(f, managed):
                f.unlink()
                print(f"  ✅ Removed legacy hook file: {f}")
                removed = True

    return removed


def _managed_hook_filenames(project_root: Path) -> set:
    """Return basenames of hook scripts managed by any supported source."""
    names = set()
    for agent_id in HOOKS_SOURCES:
        try:
            config = _load_hooks_source(project_root, agent_id)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            continue
        for _event, _matcher, hook in _iter_hook_handlers(config):
            location = _hook_script_argument(hook)
            if location is None:
                continue
            field, index = location
            if field == "args":
                token = hook["args"][index]
            else:
                try:
                    token = shlex.split(hook.get("command", ""))[index]
                except (IndexError, ValueError):
                    continue
            if isinstance(token, str) and token.endswith(".py"):
                names.add(Path(token).name)
    return names


def _is_managed_legacy_hook(path: Path, managed_names: set) -> bool:
    """True only for files the installer itself placed in the legacy hooks dir.

    A file qualifies when its name matches a hook script from one of the
    supported host-specific sources, or when its content carries the installer
    marker block.
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
    """Build a TOML config block for Kimi Code hooks."""
    lines = [f"# {PROTEIN_DESIGN_MARKER} start"]
    for event_name, matcher, hook in _iter_hook_handlers(hooks_config):
        cmd = hook.get("command", "")
        timeout = hook.get("timeout", 5)
        lines.append("[[hooks]]")
        lines.append(f'event = "{_escape_toml_string(event_name)}"')
        if matcher:
            lines.append(f'matcher = "{_escape_toml_string(matcher)}"')
        lines.append(f'command = "{_escape_toml_string(str(cmd))}"')
        args = hook.get("args")
        if isinstance(args, list):
            encoded_args = ", ".join(
                f'"{_escape_toml_string(str(value))}"' for value in args
            )
            lines.append(f"args = [{encoded_args}]")
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
    agents: Optional[List[str]] = None,
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
            all_ok = False
            continue

        if local and not cfg["supports_local"]:
            print(f"⚠️  {cfg['name']} does not support project-local hooks. Skipping.")
            all_ok = False
            continue

        config_path = cfg["local_config"] if local else cfg["global_config"]

        print(f"── {cfg['name']} ({config_path}) ──")
        try:
            if uninstall:
                if agent_id == "claude":
                    operation_ok = _uninstall_claude(config_path)
                elif agent_id == "codex":
                    scope = "local" if local else "global"
                    operation_ok = _uninstall_codex(
                        config_path,
                        scope=scope,
                        cleanup_legacy=not local,
                    )
                elif agent_id == "kimi":
                    operation_ok = _uninstall_kimi(config_path)
                else:
                    operation_ok = False
                if operation_ok is False:
                    all_ok = False
                continue

            hooks_config = _load_hooks_source(project_root, agent_id)
            hooks_config = _rewrite_hook_commands(hooks_config, project_root)

            if agent_id == "claude":
                operation_ok = _install_claude(config_path, hooks_config, force=force)
            elif agent_id == "codex":
                operation_ok = _install_codex(config_path, hooks_config, force=force)
            elif agent_id == "kimi":
                operation_ok = _install_kimi(config_path, hooks_config, force=force)
            else:
                operation_ok = False
            if operation_ok is False:
                all_ok = False
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


def _count_protein_hooks(data: object) -> int:
    """Count Protein Design hooks in nested or flat JSON data."""
    return sum(
        1
        for _event, _matcher, hook in _iter_hook_handlers(data)
        if _is_our_hook_command(hook)
    )


def _validate_claude_plugin_manifest(plugin_data: dict) -> List[str]:
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


def _validate_hook_source(data: object, project_root: Path, source_name: str) -> List[str]:
    """Validate a nested or flat hook source and its script targets."""
    errors = []
    if not isinstance(data, (dict, list)):
        return [f"{source_name} must contain an object or array"]
    if isinstance(data, dict) and "hooks" not in data:
        return [f"{source_name} is missing top-level 'hooks'"]
    count = 0
    for _event, _matcher, hook in _iter_hook_handlers(data):
        count += 1
        platforms = [None]
        if "commandWindows" in hook:
            platforms.append("win32")
        for platform in platforms:
            location = _hook_script_argument(hook, platform=platform)
            label = "commandWindows" if platform else "command"
            if location is None:
                errors.append(f"{source_name} hook has no .py script target in {label}: {hook!r}")
                continue
            field, index = location
            if field == "args":
                script_arg = hook["args"][index]
            else:
                command = _hook_command_value(hook, platform=platform)
                try:
                    script_arg = _split_shell_tokens(command, platform=platform)[index]
                except (IndexError, ValueError):
                    errors.append(f"{source_name} hook has invalid {label}: {hook!r}")
                    continue
            try:
                script_path = _resolve_hook_script(script_arg, project_root)
            except ValueError as exc:
                errors.append(f"{source_name} hook has invalid script in {label}: {exc}")
                continue
            if not script_path.exists():
                errors.append(f"{source_name} hook script does not exist: {script_path}")
    if count == 0:
        errors.append(f"{source_name} contains no hooks")
    return errors


def _validate_marketplace_manifest(marketplace_data: dict) -> List[str]:
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
        "Claude hooks source": project_root / "hooks" / "hooks.json",
        "Codex hooks source": project_root / "hooks" / "codex-hooks.json",
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

            if label in ("Claude hooks source", "Codex hooks source"):
                source_errors = _validate_hook_source(data, project_root, label)
                if source_errors:
                    for error in source_errors:
                        print(f"  ❌ {error}")
                    ok = False
                else:
                    print(f"  ✅ Valid hooks config ({_count_protein_hooks(data)} hooks)")
                    print("  ✅ All referenced hook scripts exist and are inside protein_design/hooks")
            elif label == "Kimi plugin manifest":
                if "name" not in data:
                    print(f"  ❌ Missing required 'name' field")
                    ok = False
                else:
                    print(f"  ✅ Valid manifest (name: {data['name']})")
                source_errors = _validate_hook_source(data, project_root, label)
                if source_errors:
                    for error in source_errors:
                        print(f"  ❌ {error}")
                    ok = False
            elif "plugin" in label.lower():
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

    # Filter valid agents from positional args. A mixed valid/invalid request
    # still exits non-zero so callers can detect that not every target ran.
    agents = None
    invalid_agents = False
    if args.agents:
        agents = [a for a in args.agents if a in AGENT_CONFIGS]
        invalid = [a for a in args.agents if a not in AGENT_CONFIGS]
        if invalid:
            print(f"⚠️  Unknown agents (ignored): {invalid}")
            invalid_agents = True
        if not agents:
            print(f"No valid agents specified. Valid: {list(AGENT_CONFIGS.keys())}")
            sys.exit(1)

    ok = install_hooks(agents=agents, local=args.local, force=args.force, uninstall=args.uninstall)
    sys.exit(0 if ok and not invalid_agents else 1)
