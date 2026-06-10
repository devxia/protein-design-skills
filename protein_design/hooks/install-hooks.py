#!/usr/bin/env python3
"""Cross-agent hook installer for the Protein Design plugin.

Detects installed coding agents and installs hook scripts for each:
  - Claude Code: registers hooks in ~/.claude/settings.json
  - Kimi Code: copies hooks to ~/.kimi-code/hooks/ and updates ~/.kimi-code/config.toml
  - Codex CLI: registers hooks in ~/.codex/settings.json

Run this after installing the plugin.
"""

import json
import os
import shutil
import sys
from pathlib import Path

HOOKS = [
    ("protein-context-inject.py", "UserPromptSubmit"),
    ("tool-recommender.py", "UserPromptSubmit"),
    ("gpu-check-hook.py", "PreToolUse"),
    ("design-complete-notify.py", "PostToolUse"),
    ("error-recovery.py", "PostToolUse"),
    ("background-notify.py", "Notification"),
]

MATCHERS = {
    "UserPromptSubmit": "(?i)(protein|pdb|binder|alphafold|rfdiffusion|proteinmpnn|design|structure|sequence|residue|loop|scaffold|diffusion|mpnn|fold|validation|filter|rank)",
    "PreToolUse": "mcp__.*__submit_job",
    "PostToolUse": "mcp__.*__query_job|mcp__.*__execute_tool",
    "Notification": r"task\\.(completed|failed|killed|timeout)",
}

# ── Agent-specific hook configs ──────────────────────────────────────────

AGENT_CONFIGS = {
    "kimi": {
        "name": "Kimi Code",
        "hooks_dir": Path.home() / ".kimi-code" / "hooks",
        "config_path": Path.home() / ".kimi-code" / "config.toml",
        "format": "toml",
    },
    "claude": {
        "name": "Claude Code",
        "hooks_dir": Path.home() / ".claude" / "hooks",
        "config_path": Path.home() / ".claude" / "settings.json",
        "format": "json",
    },
    "codex": {
        "name": "Codex CLI",
        "hooks_dir": Path.home() / ".codex" / "hooks",
        "config_path": Path.home() / ".codex" / "settings.json",
        "format": "json",
    },
}


def _detect_agents() -> list[str]:
    """Detect which coding agents are available on this machine."""
    available = []
    for agent_id, cfg in AGENT_CONFIGS.items():
        if cfg["config_path"].exists() or cfg["hooks_dir"].exists():
            available.append(agent_id)
    return available


def _install_for_kimi(source_dir: Path) -> bool:
    """Install hooks for Kimi Code (TOML config format)."""
    cfg = AGENT_CONFIGS["kimi"]
    hooks_dir = cfg["hooks_dir"]
    config_path = cfg["config_path"]
    hooks_dir.mkdir(parents=True, exist_ok=True)

    installed = []
    for filename, event in HOOKS:
        src = source_dir / filename
        if not src.exists():
            print(f"  ⚠️  Source not found: {src}")
            continue
        dst = hooks_dir / filename
        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
        installed.append((filename, event))
        print(f"  ✅ Installed: {dst}")

    if not installed:
        return False

    # Register in TOML config
    config_entries = []
    for filename, event in installed:
        matcher = MATCHERS[event]
        config_entries.append(
            f'[[hooks]]\nevent = "{event}"\nmatcher = "{matcher}"\n'
            f'command = "python {hooks_dir / filename}"\ntimeout = 5\n'
        )
    config_block = "\n".join(config_entries)

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            existing = f.read()
        if "protein-context-inject" in existing:
            print("\n  ⚠️  Kimi Code config already has protein design hooks. Skipping registration.")
            return True
        with open(config_path, "a", encoding="utf-8") as f:
            f.write(f"\n# Protein Design hooks\n{config_block}\n")
    else:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"# Kimi Code configuration\n\n# Protein Design hooks\n{config_block}\n")

    print(f"  ✅ Registered {len(installed)} hooks in {config_path}")
    return True


def _install_for_json_agent(agent_id: str, source_dir: Path) -> bool:
    """Install hooks for JSON-config agents (Claude Code, Codex CLI)."""
    cfg = AGENT_CONFIGS[agent_id]
    hooks_dir = cfg["hooks_dir"]
    config_path = cfg["config_path"]
    hooks_dir.mkdir(parents=True, exist_ok=True)

    installed = []
    for filename, event in HOOKS:
        src = source_dir / filename
        if not src.exists():
            print(f"  ⚠️  Source not found: {src}")
            continue
        dst = hooks_dir / filename
        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
        installed.append((filename, event))
        print(f"  ✅ Installed: {dst}")

    if not installed:
        return False

    # Read existing settings.json
    settings = {}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            print(f"  ⚠️  {config_path} is invalid JSON — backing up and recreating")
            shutil.copy2(config_path, config_path.with_suffix(".json.bak"))
            settings = {}

    # Build hook entries
    existing_hooks = settings.get("hooks", [])
    hook_commands = set()
    for h in existing_hooks:
        cmd = h.get("command", "")
        hook_commands.add(cmd)

    new_hooks = []
    for filename, event in installed:
        matcher = MATCHERS[event]
        hook_cmd = f"python {hooks_dir / filename}"
        if hook_cmd in hook_commands:
            print(f"  ⚠️  Hook already registered: {filename}")
            continue
        new_hooks.append({
            "event": event,
            "matcher": matcher,
            "command": hook_cmd,
            "timeout": 5,
        })

    if new_hooks:
        settings["hooks"] = existing_hooks + new_hooks
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        print(f"  ✅ Registered {len(new_hooks)} hooks in {config_path}")
    else:
        print("  ℹ️  All hooks already registered.")

    return True


def install_hooks(agents: list[str] | None = None) -> None:
    """Install hook scripts for detected or specified coding agents.

    Args:
        agents: List of agent IDs to install for (e.g. ['claude', 'kimi']).
                If None, auto-detects available agents.
    """
    source_dir = Path(__file__).parent.resolve()

    if agents is None:
        agents = _detect_agents()

    if not agents:
        print("No supported coding agents detected on this system.")
        print("\nSupported agents:")
        for agent_id, cfg in AGENT_CONFIGS.items():
            print(f"  - {cfg['name']} ({cfg['hooks_dir']})")
        print("\nInstall an agent first, then re-run this script.")
        print("Or specify agents manually: python install-hooks.py claude kimi")
        sys.exit(1)

    print(f"Installing Protein Design hooks for detected agents: {', '.join(AGENT_CONFIGS[a]['name'] for a in agents)}\n")

    for agent_id in agents:
        cfg = AGENT_CONFIGS.get(agent_id)
        if not cfg:
            print(f"⚠️  Unknown agent: {agent_id}. Skipping.")
            continue

        print(f"── {cfg['name']} ──")
        try:
            if cfg["format"] == "toml":
                _install_for_kimi(source_dir)
            elif cfg["format"] == "json":
                _install_for_json_agent(agent_id, source_dir)
        except Exception as exc:
            print(f"  ❌ Failed to install for {cfg['name']}: {exc}")
        print()

    print("📝 Next steps:")
    print("   - Review the config files listed above to customize settings")
    print("   - Restart your coding agent or start a new session")
    print("   - Hooks will be active in the new session")


if __name__ == "__main__":
    # Allow passing agent names via CLI: python install-hooks.py claude kimi
    if len(sys.argv) > 1:
        agents = [a for a in sys.argv[1:] if a in AGENT_CONFIGS]
        if not agents:
            print(f"Unknown agents: {sys.argv[1:]}")
            print(f"Valid agents: {list(AGENT_CONFIGS.keys())}")
            sys.exit(1)
        install_hooks(agents)
    else:
        install_hooks()
