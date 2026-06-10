---
name: config-management
description: Manage plugin configuration through natural language
---

# Configuration Management

## When to Trigger

- User says "configure", "set path", "where is", "install location"
- User wants to change output directory
- User asks about tool paths or conda environments
- User wants to check current configuration
- User says "my databases are at", "my tools are in"

## Current Configuration

The plugin reads configuration from (in priority order):
1. **Environment variables** (highest priority)
2. **Config file** (`~/.protein-design/config.yaml`)
3. **Auto-detection** (lowest priority)

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `RFDIFFUSION_PATH` | RFdiffusion installation directory | `~/software/RFdiffusion` |
| `PROTEINMPNN_PATH` | ProteinMPNN installation directory | `~/software/ProteinMPNN` |
| `ALPHAFOLD_PATH` | AlphaFold3 installation directory | `~/software/alphafold3` |
| `PROTEIN_DESIGN_OUTPUT_DIR` | Default output directory | `/tmp/protein-design` |
| `PROTEIN_DESIGN_MAX_JOBS` | Max concurrent jobs | `4` |

### Config File (`~/.protein-design/config.yaml`)

```yaml
rfdiffusion_path: /home/user/software/RFdiffusion
proteinmpnn_path: /home/user/software/ProteinMPNN
alphafold_path: /home/user/software/alphafold3
db_dir: /home/user/public_databases
output_dir: /tmp/protein-design
max_jobs: 4
rfdiffusion_conda_env: SE3nv
proteinmpnn_conda_env: proteinmpnn
alphafold_conda_env: alphafold
```

## Natural Language Configuration

Instead of explicit `configure_tool_path` MCP calls, users can simply tell the agent:

### Setting Tool Paths

```
User: My RFdiffusion is at ~/software/RFdiffusion
→ Plugin auto-configures RFDIFFUSION_PATH

User: ProteinMPNN uses conda env "mpnn"
→ Plugin saves proteinmpnn_conda_env to config

User: I have all tools in /opt/protein-tools
→ Plugin detects and configures all tools
```

### Setting Database Path

```
User: My AlphaFold databases are at /data/databases
→ Plugin auto-detects valid database subdirectories
→ Saves to config if valid

User: Check database status
→ Plugin shows detected databases, sizes, and completeness
```

### Checking Configuration

```
User: What's my current config?
→ Plugin shows all configured paths, detected tools, and environment

User: Are my tools properly configured?
→ Plugin runs check_all_tools and reports status
```

### Setting Output Directory

```
User: Save outputs to ~/protein-design-results
→ Plugin sets PROTEIN_DESIGN_OUTPUT_DIR

User: Use /tmp for outputs
→ Plugin sets output_dir to /tmp
```

## Auto-Detection

The plugin automatically searches common locations:

### RFdiffusion
- `./RFdiffusion`
- `~/RFdiffusion`
- `/opt/RFdiffusion`
- Conda environments with `rfdiffusion` package

### ProteinMPNN
- `./ProteinMPNN`
- `~/ProteinMPNN`
- `/opt/ProteinMPNN`

### AlphaFold3
- `./alphafold3`
- `~/alphafold3`
- `/opt/alphafold3`

### Databases
- `~/public_databases`
- `~/databases`
- `/opt/public_databases`

## Configuration Commands

### Via MCP Tools (Explicit)

```json
{"tool": "configure_tool_path", "params": {
  "tool_name": "rfdiffusion",
  "path": "~/software/RFdiffusion",
  "conda_env": "SE3nv"
}}
```

```json
{"tool": "configure_db_dir", "params": {
  "path": "~/public_databases"
}}
```

### Via Conversation (Implicit)

The agent interprets natural language and auto-configures:

```
User: "RFdiffusion is in ~/software/RFdiffusion, SE3nv env"
→ Agent calls configure_tool_path automatically

User: "Databases at /data/public_databases"
→ Agent calls configure_db_dir automatically

User: "max 8 jobs"
→ Agent sets PROTEIN_DESIGN_MAX_JOBS=8
```

## Tips

- Configuration persists across sessions (saved to `~/.protein-design/config.yaml`)
- Environment variables override config file settings
- Auto-detection runs on every session start
- Use `check_all_tools` to verify configuration
- Legacy `~/.kimi-protein-design/` config is also supported for migration
