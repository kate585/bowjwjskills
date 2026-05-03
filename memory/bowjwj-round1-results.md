---
name: bowjwj-round1-results
description: Round 1 (2026-05-01) CTR results baseline — 11/12 templates 5.4-7.1% CTR, S1=1.1% flagged for optimization
type: project
originSessionId: 6205bd1d-7b68-4f61-aa39-c50936691099
---
First full send round completed 2026-05-01. 12 campaigns, 120 packs, ~13,000 actual sends (after dedup), 12 agent lines.

**Why:** This is the baseline against which all future CTR improvements are measured. S1b variant was deployed to fix the only underperformer.

**How to apply:** Compare future runs against these numbers. Any template dropping >2% from this baseline needs investigation.

## Results
Globe (all ≥5%):
- G1 account-expiry: 5.7% (1239 sent, 133 clicks)
- G2 tomorrow-expiry: 7.1% (1005 sent, 113 clicks)
- G3 suspense: 6.1% (1064 sent, 111 clicks)
- G4 update-amount: 5.9% (1125 sent, 120 clicks)
- G5 friend-expiry: 6.1% (1169 sent, 115 clicks)
- G6 small-easy: 5.5% (994 sent, 74 clicks)

Smart:
- S1 account-expiry: 1.1% (1689 sent, 20 clicks) ← REPLACED with S1b
- S2 update-amount: 6.9% (1017 sent, 115 clicks)
- S3 suspense: 7.0% (1036 sent, 126 clicks)
- S4 friend-tone: 5.5% (1127 sent, 124 clicks)
- S5 expiry-pressure: 6.1% (1011 sent, 98 clicks)
- S6 conversation: 5.4% (1079 sent, 114 clicks)

## Key findings
- Globe average CTR: 6.07%
- Smart average CTR (excl S1): 6.18%
- Dedup rate: 45-65% (cleanCount=200 → actual send 65-109)
- S1 failure diagnosis: {$phone[4]} (4-digit) less trusted than {$phone[10]} (full number); Smart spam filter stricter
- S1b fix: conversational Taglish opener "i-check mo na, baka nandyan na..." (matching high-CTR S3 style at 7.0%)
