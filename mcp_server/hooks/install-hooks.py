#!/usr/bin/env python3
"""One-click installer for Kimi Protein Design hooks.

Copies hook scripts to ~/.kimi-code/hooks/ and registers them in
~/.kimi-code/config.toml. Run this after installing the plugin.
"""

import os
import shutil
from pathlib import Path

HOOKS = [
    ("protein-context-inject.py", "UserPromptSubmit"),
    ("gpu-check-hook.py", "PreToolUse"),
    ("design-complete-notify.py", "PostToolUse"),
    ("background-notify.py", "Notification"),
]

MATCHERS = {
    "UserPromptSubmit": "(?i)(protein|pdb|binder|alphafold|rfdiffusion|proteinmpnn|design|structure|sequence|residue|loop|scaffold)",
    "PreToolUse": "mcp__.*__submit_job",
    "PostToolUse": "mcp__.*__query_job",
    "Notification": "task\\.completed|task\\.failed|task\\.killed",
}


def install_hooks() -> None:
    """Install all hook scripts and register in config.toml."""
    hooks_dir = Path.home() / ".kimi-code" / "hooks"
    config_path = Path.home() / ".kimi-code" / "config.toml"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Source directory: same directory as this script
    source_dir = Path(__file__).parent.resolve()

    installed = []
    for filename, event in HOOKS:
        src = source_dir / filename
        dst = hooks_dir / filename

        if not src.exists():
            print(f"⚠️  Source not found: {src}")
            continue

        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
        installed.append((filename, event))
        print(f"✅ Installed: {dst}")

    # Update config.toml
    config_entries = []
    for filename, event in installed:
        matcher = MATCHERS[event]
        config_entries.append(
            f"""[[hooks]]
event = "{event}"
matcher = "{matcher}"
command = "python {hooks_dir / filename}"
timeout = 5
"""
        )

    config_block = "\n".join(config_entries)

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            existing = f.read()
        # Avoid duplicates
        if "protein-context-inject" in existing:
            print("\n⚠️  config.toml already contains protein design hooks. Skipping registration.")
            print("   If you want to reinstall, remove existing hooks from config.toml first.")
            return
        with open(config_path, "a", encoding="utf-8") as f:
            f.write(f"\n# Kimi Protein Design hooks\n{config_block}\n")
    else:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"# Kimi Code configuration\n\n# Kimi Protein Design hooks\n{config_block}\n")

    print(f"\n✅ Registered {len(installed)} hooks in {config_path}")
    print("\n📝 Next steps:")
    print("   1. Review ~/.kimi-code/config.toml to customize settings")
    print("   2. Run /new to start a fresh Kimi Code session")
    print("   3. Hooks will be active in the new session")


if __name__ == "__main__":
    install_hooks()
