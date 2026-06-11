---
name: periodic-summary
description: Guide users on setting up periodic progress summaries for protein design pipelines with artifact counts, quality metrics, and notifications
---

# Periodic Progress Summary Guide

**Get regular updates on your protein design campaign without constantly checking files.**

This skill covers three ways to receive periodic summaries of backbone counts, sequence counts, validation results, and quality distributions.

---

## Method 1: One-Shot Summary (Run Anytime)

```bash
# Single directory summary
python scripts/summarize_outputs.py --output-dir outputs/

# Project-wide dashboard across all discovered stages
python scripts/project_dashboard.py --output-dir outputs/

# With expected counts for progress bars
python scripts/project_dashboard.py --output-dir outputs/ \
  --expected-backbones 50 \
  --expected-sequences 400 \
  --expected-validations 50
```

**What you get / 输出内容：**
- Backbone / 骨架 PDB count
- Sequence / 序列 FASTA count
- Validation / 验证 result count
- Mean / best / worst pLDDT
- Quality distribution (Excellent ≥90 / Good 80-89 / Acceptable 70-79 / Poor <70)
- Top designs ranked by pLDDT
- Next-step recommendation / 下一步建议

---

## Method 2: Live Watch Mode (Auto-Refresh)

```bash
# Refresh every 30 seconds until interrupted (Ctrl+C)
python scripts/summarize_outputs.py --output-dir outputs/ --watch

# Project dashboard with live refresh
python scripts/project_dashboard.py --output-dir outputs/ --watch

# Custom refresh interval (seconds)
python scripts/summarize_outputs.py --output-dir outputs/ --watch --interval 60
```

**Best for:** Long-running validations where you want a continuously updating terminal view.

---

## Method 3: Background Job + Periodic Check (Fully Automated)

Use `scripts/job_manager.py` to run stages in the background, then check progress on a schedule:

```bash
# 1. Submit a background design job
JOB_ID=$(python scripts/job_manager.py submit --name rfdiff -- \
  python scripts/run_rfdiffusion.py --contig "150-150" --num-designs 50)

# 2. Wait for completion with automatic status updates
python scripts/job_manager.py wait $JOB_ID --timeout 3600

# 3. Summary runs automatically after each stage if hooks are installed
#    (progress-reporter hook fires on PostToolUse)

# 4. For periodic checks while jobs run, use watch mode in another terminal:
python scripts/project_dashboard.py --output-dir outputs/ --watch
```

---

## Hook-Based Automatic Summaries

If you installed hooks, progress summaries fire automatically:

```bash
python protein_design/hooks/install-hooks.py
```

| When | Hook | What It Reports |
|------|------|-----------------|
| After each pipeline stage | `progress-reporter.py` | Artifact counts + next-step hint |
| After validation/filtering | `progress-reporter.py` | Quality distribution + top designs |
| When you ask about progress | `progress-query-helper.py` | Command suggestions + quick snapshot |
| When background task finishes | `background-notify.py` | Desktop notification |
| On session start (protein topic) | `user-onboarding.py` | Available commands + reminders |

---

## Interpreting the Summary Output

```
📈 [VALIDATION STAGE COMPLETE] Progress Summary
   Output directory: outputs/af3

   Artifact Counts:
      • Backbone PDB files:     50
      • Sequence FASTA files:   200
      • Predicted structures:   48
      • Confidence JSON files:  48

   Quality Metrics:
      • Mean pLDDT:           84.3
      • Mean ipTM:            0.712
      • Excellent (≥90):      8
      • Good (80-89):         22
      • Acceptable (70-79):   14
      • Poor (<70):           4

   Top Designs by pLDDT:
      • design_12: pLDDT=94.2 ipTM=0.823
      • design_03: pLDDT=91.7 ipTM=0.801
      • design_27: pLDDT=89.4 ipTM=0.756

   💡 Next: Run filtering to rank designs by pLDDT / ipTM thresholds.
```

**What the numbers mean:**
- **pLDDT ≥ 90**: Very high confidence — excellent candidate for experimental validation
- **pLDDT 80–89**: Good confidence — likely correct overall fold
- **pLDDT 70–79**: Acceptable — may have local issues, inspect visually
- **pLDDT < 70**: Poor — likely incorrect, redesign or filter out
- **ipTM ≥ 0.8**: Strong binder interface prediction (for complexes)
- **ipTM 0.6–0.8**: Moderate interface confidence
- **ipTM < 0.6**: Weak interface — consider redesign

---

## Setting Up a Recurring Cron Summary

For campaigns that run over hours or days, schedule a recurring summary command:

```bash
# Every 30 minutes, append a summary to campaign.log
*/30 * * * * cd /path/to/project && python scripts/project_dashboard.py \
  --output-dir outputs/ >> campaign.log 2>&1
```

Or use the Claude `/loop` feature:

```
/loop every 10m summarize protein design progress in /Volumes/data/项目：VibeCoding/protein-design-skills
```

---

## Multi-Stage Campaign Tracking

For a complete design campaign, track these expected outputs:

| Stage | Input | Expected Output | Check Command |
|-------|-------|-----------------|---------------|
| 0. Preprocessing | `target.pdb` | 1 fixed PDB | `ls outputs/preprocessed/*.pdb` |
| 1. Backbone | fixed PDB | N backbone PDBs | `ls outputs/backbones/*.pdb \| wc -l` |
| 2. Sequence | N PDBs | N × k FASTAs | `ls outputs/seqs/*.fa \| wc -l` |
| 3. Validation | FASTAs + JSON | N predictions | `find outputs/af3 -name confidence.json \| wc -l` |
| 4. Filtering | predictions | Top-ranked subset | `ls outputs/filtered/*.csv` |

### New workflow outputs (also counted automatically / 新增流程也会被自动统计)

The dashboard and hooks count outputs from all skills, including the newer workflows:

| Skill / 技能 | Output type / 产物类型 | Typical extension |
|--------------|------------------------|-------------------|
| `framediff-backbone` | Backbone PDBs | `.pdb` |
| `protpardelle-allatom` | All-atom PDBs (backbone + side chains) | `.pdb` |
| `pifold-sequence-design` | Designed sequences | `.fa` / `.fasta` |
| `dima-workflow` | Generated sequences from pLM latents | `.fa` / `.fasta` |
| `proteindt-workflow` | Text-guided sequences | `.fa` / `.fasta` |
| `pro-ldm-workflow` | Fitness-conditional sequences | `.fa` / `.fasta` |
| `bioemu-ensemble` | Conformational ensemble trajectories | `.pdb` / `.xtc` |
| `diffdock-ligand` | Docked ligand poses + confidence scores | `.sdf` / `.pdb` |
| `progen2-sequence` | Autoregressive PLM-generated sequences | `.fa` / `.fasta` |
| `boltz2-validation` | Predicted structures + affinity scores | `.cif` / `affinity*.json` |
| `boltzdesign1-binder` | Designed binder complexes + confidence CSV | `.pdb` / `.csv` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No output files detected` | Run a pipeline stage first, or point to the correct `--output-dir` |
| `Confidence JSON not found` | Validation may still be running; use `--watch` mode |
| Quality metrics look wrong | Check that `confidence.json` matches the expected schema (AF3, Boltz, Chai, etc.) |
| Watch mode uses too much CPU | Increase `--interval` to 120 or 300 seconds |

---

## See Also

- `full-pipeline` — End-to-end pipeline guide
- `job-monitor` — Background job management
- `pipeline-selection` — Choose the right workflow
- `quickstart-guide` — Get started with your first design
