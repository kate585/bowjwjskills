---
name: bowjwj-recap-ctr-display
description: All recap/status displays must include average CTR values per carrier and overall
type: feedback
originSessionId: f62da09f-d1a6-493b-9589-793d040a7e60
---
Any time the status, recap, or monitor output is displayed, it MUST include:
- **平均 CTR per 运营商** (Globe / Smart) — per-carrier average across all active templates
- **整体平均 CTR** — combined average
- Latest batch-level CTR numbers

**Why:** Willy wants the average CTR visible at all times in recap/status output. No recap without CTR.

**How to apply:** When showing send status, round results, monitor output, or daily recap — always compute and display average CTR per carrier and overall. Format: `Globe AVG CTR: X.X% | Smart AVG CTR: X.X% | Overall AVG: X.X%`
