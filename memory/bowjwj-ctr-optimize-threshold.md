---
name: bowjwj-ctr-optimize-threshold
description: Iron rule — CTR<3% triggers immediate copy optimization: force direction rotation + generate fresh Taglish templates
type: feedback
originSessionId: fcd7942e-86b2-4e47-aaea-d126778c52b1
---
CTR<3% triggers automatic copy optimization. No waiting — every 5 rounds, if recent (30 min window) CTR is below 3% with ≥50 sends, the system:

1. Forces direction rotation (G1→G2, S1→S2, etc.) to try a different copy angle
2. Generates fresh Taglish templates via AI
3. Refreshes prereq to pick up the new templates

**Why:** CTR<3% means the current copy direction isn't resonating. Round 1 proved Globe averages 6.07% and Smart 6.18% — anything below 3% is 50% below baseline and needs immediate correction.

**How to apply:**
- Checked every 5 rounds (aligned with refresh_best_template cycle)
- 30-minute lookback window for CTR data
- Minimum 50 sends required before triggering (statistical significance floor)
- Operations: force rotation + generate_taglish_template + fetch_prereq
- Does NOT stop sending — continues with optimized copy
- CTR=0% and CTR<1% rules (from bowjwj-zerocTR-optimize) still take precedence
