#!/usr/bin/env python3
"""PostToolUse hook: compare results from multiple validation tools.

When designs are validated with multiple tools (e.g., AlphaFold3 + Boltz-1 + Chai-1),
this hook automatically compares confidence metrics and highlights agreements/disagreements.
"""

import json
import sys
from typing import Any


def main() -> int:
    """Main entry point."""
    try:
        text = sys.stdin.read()
        data = json.loads(text) if text.strip() else {}
    except Exception:
        return 0

    # Only activate for validation tool completions
    tool_name = str(data.get("tool", "")).lower()
    if not any(t in tool_name for t in ["alphafold", "boltz", "chai", "omegafold", "esmfold", "protenix"]):
        return 0

    # This is a template — the actual comparison would require
    # access to multiple result sets, which hooks receive one at a time.
    # The hook serves as a reminder to compare when multiple validators are used.

    output = """[Design Comparator] Validation complete.

## Cross-Validation Strategy

If you ran multiple validators, compare their results:

### Agreement Analysis
```python
# Compare pLDDT across tools
comparison = {
    "AlphaFold3": {"plddt": 85.2, "ptm": 0.82, "iptm": 0.88},
    "Boltz-1": {"plddt": 83.1, "ptm": 0.80, "iptm": 0.85},
    "Chai-1": {"plddt": 84.5, "ptm": 0.81, "iptm": 0.87},
}

# High agreement = high confidence
# Low agreement = investigate (may indicate model-specific bias)
```

### Interpreting Disagreements

| Pattern | Interpretation | Action |
|---------|---------------|--------|
| All tools agree | High confidence design | Proceed to experiments |
| AF3 high, others low | May be MSA-dependent | Check MSA quality |
| Boltz/Chai high, AF3 low | May be complex-specific | Validate with more samples |
| ESMFold/OmegaFold low, others high | Fast tools may miss details | Trust slower tools |
| All tools low | Design is likely poor | Regenerate |

### Ranking Strategy

For designs validated with multiple tools, compute an ensemble score:

```python
import numpy as np

def ensemble_score(results):
    \"\"\"Average metrics across validators.\"\"\"
    plddts = [r["plddt"] for r in results.values()]
    ptms = [r["ptm"] for r in results.values()]
    return {
        "mean_plddt": np.mean(plddts),
        "std_plddt": np.std(plddts),
        "mean_ptm": np.mean(ptms),
        "agreement": 1 - np.std(plddts)/np.mean(plddts),  # Higher = more agreement
    }
```

### Tips

- **Two validators minimum**: Run at least 2 different tools for critical designs
- **Boltz-1 + Chai-1**: Good pair (different architectures, both permissive licenses)
- **AF3 + Boltz-1**: Good pair (gold standard + commercial-friendly)
- **ESMFold (screen) + AF3 (validate)**: Efficient for large libraries
- **Protenix (multi-sample)**: Use 100-1000 samples for highest confidence
"""

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
