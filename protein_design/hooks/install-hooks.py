#!/usr/bin/env python3
"""Cross-agent hook installer for the Protein Design plugin.

Detects installed coding agents and installs hook scripts for each:
  - Claude Code: registers hooks in ~/.claude/settings.json
  - Kimi Code: copies hooks to ~/.kimi-code/hooks/ and updates ~/.kimi-code/config.toml
  - Codex CLI: registers hooks in ~/.codex/settings.json

Run this after installing the plugin:

  python install-hooks.py

This installer uses Skills + Hooks + Standalone Scripts only.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HOOKS = [
    ("user-onboarding.py", "UserPromptSubmit"),
    ("session-health-check.py", "UserPromptSubmit"),
    ("protein-context-inject.py", "UserPromptSubmit"),
    ("tool-recommender.py", "UserPromptSubmit"),
    ("alternative-tool-recommender.py", "PreToolUse"),
    ("auto-parameter-tuner.py", "UserPromptSubmit"),
    ("batch-orchestrator.py", "UserPromptSubmit"),
    ("progress-query-helper.py", "UserPromptSubmit"),
    ("cost-estimator.py", "UserPromptSubmit"),
    ("execution-adapter.py", "PreToolUse"),
    ("parameter-generator.py", "UserPromptSubmit"),
    ("gpu-check-hook.py", "PreToolUse"),
    ("design-complete-notify.py", "PostToolUse"),
    ("design-comparator.py", "PostToolUse"),
    ("design-report.py", "PostToolUse"),
    ("error-recovery.py", "PostToolUse"),
    ("format-converter.py", "PostToolUse"),
    ("job-monitor.py", "PostToolUse"),
    ("pipeline-orchestrator.py", "PostToolUse"),
    ("quality-gate.py", "PostToolUse"),
    ("progress-reporter.py", "Notification"),
    ("background-notify.py", "Notification"),
]

MATCHERS = {
    "UserPromptSubmit": "(?i)(protein|pdb|binder|alphafold|rfdiffusion|proteinmpnn|design|structure|sequence|residue|loop|scaffold|diffusion|mpnn|fold|validation|filter|rank)",
    "PreToolUse": "(?i)(run_pdbfixer|run_rfdiffusion|run_proteinmpnn|run_alphafold|run_filtering|run_boltz|run_chai|run_esmfold|run_omegafold)",
    "PostToolUse": "(?i)(run_pdbfixer|run_rfdiffusion|run_proteinmpnn|run_alphafold|run_filtering|run_boltz|run_chai|run_esmfold|run_omegafold|batch_runner|job_manager)",
    "Notification": r"task\.(completed|failed|killed|timeout)",
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


def _detect_agents() -> list[str]:
    """Detect which coding agents are available on this machine."""
    available = []
    for agent_id, cfg in AGENT_CONFIGS.items():
        if cfg["config_path"].exists() or cfg["hooks_dir"].exists():
            available.append(agent_id)
    return available


def _install_for_kimi(source_dir: Path, force: bool = False) -> bool:
    """Install hooks for Kimi Code (TOML config format).

    Args:
        source_dir: Directory containing hook source files.
        force: If True, reinstall hooks even if already registered.
    """
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
        if "protein-context-inject" in existing and not force:
            print("\n  ⚠️  Kimi Code config already has protein design hooks. Skipping registration.")
            return True
        with open(config_path, "a", encoding="utf-8") as f:
            f.write(f"\n# Protein Design hooks\n{config_block}\n")
    else:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"# Kimi Code configuration\n\n# Protein Design hooks\n{config_block}\n")

    # Add hook instructions
    with open(config_path, "a", encoding="utf-8") as f:
        f.write(f"\n{HOOK_INSTRUCTIONS}\n")
    print(f"  ✅ Hook instructions added")

    print(f"  ✅ Registered {len(installed)} hooks in {config_path}")
    return True


def _install_for_json_agent(agent_id: str, source_dir: Path, force: bool = False) -> bool:
    """Install hooks for JSON-config agents (Claude Code, Codex CLI).

    Args:
        agent_id: Agent identifier (claude, codex).
        source_dir: Directory containing hook source files.
        force: If True, reinstall hooks even if already registered.
    """
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
        if hook_cmd in hook_commands and not force:
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


def write_hooks_config(project_root: Path) -> Path:
    """Write a .hooks-config.json template to the project root."""
    config_path = project_root / ".hooks-config.json"
    config = {
        "name": "protein-design-skills",
        "description": "Configuration for protein design — skills + hooks + direct execution",
        "skills": ["./skills/"],
        "hooks": {
            "protein-context-inject": "python protein_design/hooks/protein-context-inject.py",
            "tool-recommender": "python protein_design/hooks/tool-recommender.py",
            "session-health-check": "python protein_design/hooks/session-health-check.py",
            "pipeline-orchestrator": "python protein_design/hooks/pipeline-orchestrator.py",
            "gpu-check-hook": "python protein_design/hooks/gpu-check-hook.py",
            "execution-adapter": "python protein_design/hooks/execution-adapter.py",
            "job-monitor": "python protein_design/hooks/job-monitor.py",
            "error-recovery": "python protein_design/hooks/error-recovery.py",
            "batch-orchestrator": "python protein_design/hooks/batch-orchestrator.py",
            "quality-gate": "python protein_design/hooks/quality-gate.py",
        },
        "scripts": {
            "pdbfixer": "scripts/run_pdbfixer.py",
            "rfdiffusion": "scripts/run_rfdiffusion.py",
            "proteinmpnn": "scripts/run_proteinmpnn.py",
            "alphafold3": "scripts/run_alphafold3.py",
            "boltz": "scripts/run_boltz.py",
            "chai1": "scripts/run_chai1.py",
            "omegafold": "scripts/run_omegafold.py",
            "esmfold": "scripts/run_esmfold.py",
            "filtering": "scripts/run_filtering.py",
            "convert": "scripts/convert_format.py",
            "batch": "scripts/batch_runner.py",
            "jobs": "scripts/job_manager.py",
        },
        "instructions": "Use skills for guidance, hooks for automation, and scripts for execution. Read SKILL_INDEX.md for navigation.",
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config_path


def install_hooks(agents: list[str] | None = None, force: bool = False) -> None:
    """Install hook scripts for detected or specified coding agents.

    Args:
        agents: List of agent IDs to install for (e.g. ['claude', 'kimi']).
                If None, auto-detects available agents.
        force: If True, reinstall hooks even if already registered.
    """
    source_dir = Path(__file__).parent.resolve()
    project_root = source_dir.parent.parent

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

    print(f"Installing Protein Design hooks for: {', '.join(AGENT_CONFIGS[a]['name'] for a in agents)}\n")
    print("Mode: Skills + Hooks + Standalone Scripts\n")

    for agent_id in agents:
        cfg = AGENT_CONFIGS.get(agent_id)
        if not cfg:
            print(f"⚠️  Unknown agent: {agent_id}. Skipping.")
            continue

        print(f"── {cfg['name']} ──")
        try:
            if cfg["format"] == "toml":
                _install_for_kimi(source_dir, force=force)
            elif cfg["format"] == "json":
                _install_for_json_agent(agent_id, source_dir, force=force)
        except Exception as exc:
            print(f"  ❌ Failed to install for {cfg['name']}: {exc}")
        print()

    # Write .hooks-config.json template
    hooks_config = write_hooks_config(project_root)
    print(f"📝 Created hooks config template: {hooks_config}")
    print("   Copy relevant sections to your agent's config.\n")

    print("📝 Next steps:")
    print("   1. Restart your coding agent or start a new session")
    print("   2. Hooks will fire automatically on protein-related prompts")
    print("   3. Read skill 'quickstart-guide' to get started")
    print("   4. Read skill 'pipeline-selection' to choose a design pipeline")
    print("   5. Read skill 'install-guide' to install the tools you need")


def list_hooks() -> None:
    """List hooks registered for each agent."""
    print("Protein Design Hooks — Installation Status\n")

    for agent_id, cfg in AGENT_CONFIGS.items():
        config_path = cfg["config_path"]
        hooks_dir = cfg["hooks_dir"]

        print(f"── {cfg['name']} ──")

        if not config_path.exists() and not hooks_dir.exists():
            print(f"  ❌ Not installed (config: {config_path})")
            print()
            continue

        # Check hook files
        if hooks_dir.exists():
            hook_files = list(hooks_dir.glob("*.py"))
            if hook_files:
                print(f"  📁 Hook files ({len(hook_files)}):")
                for f in sorted(hook_files):
                    print(f"     • {f.name}")
            else:
                print(f"  📁 Hook directory exists but empty: {hooks_dir}")
        else:
            print(f"  📁 No hook directory: {hooks_dir}")

        # Check registered hooks in config
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    if cfg["format"] == "json":
                        settings = json.load(f)
                        hooks = settings.get("hooks", [])
                        if hooks:
                            print(f"  ⚙️  Registered hooks ({len(hooks)}):")
                            for h in hooks:
                                event = h.get("event", "?")
                                cmd = h.get("command", "?")
                                name = Path(cmd).name if cmd else "?"
                                print(f"     • [{event}] {name}")
                        else:
                            print(f"  ⚙️  No hooks registered in config")
                    else:
                        print(f"  ⚙️  Config: {config_path}")
            except Exception as e:
                print(f"  ⚠️  Error reading config: {e}")

        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Install Protein Design hooks for coding agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect agents and install hooks
  python install-hooks.py

  # Install for specific agents
  python install-hooks.py claude kimi

  # Install for all supported agents
  python install-hooks.py claude kimi codex

  # List installed hooks
  python install-hooks.py --list
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
        "--force",
        action="store_true",
        help="Reinstall hooks even if already registered.",
    )
    args = parser.parse_args()

    if args.list:
        list_hooks()
        sys.exit(0)

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

    install_hooks(agents=agents, force=args.force)
