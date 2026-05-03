---
name: bowjwj-anticollide-strategy
description: OBSOLETE. Deep page + shuffle pack selection replaced by fixed source "凯特ai发送：银河v数据4月" page 3 only
type: feedback
originSessionId: 475654df-8077-45b9-ab85-432d0554891d
---
## Anti-collision strategy (2026-05-03 02:49 deployed)

**Problem**: 凯总巴西 project grabs all packs from front pages (1-20). Our packs all returned PHONE_PACK_ALREADY_ASSIGNED.

**Fix in fast_send.py**:
1. Deep pages first: pages 60-200 shuffled, then 1-59 shuffled, max 150 pages total
2. Pack shuffle: after filtering, `_random.shuffle(all_packs)` instead of sort by cleanCount descending
3. Reduces API calls from 300 pages → 150 pages (faster startup while still avoiding conflicts)

**Why**: Deep pages are less contested. Shuffle distributes selections across the catalog so we don't compete for the same high-cleanCount packs.

**Results**: 
- Globe Round 1: CTR 6.91% (28/405) — no conflicts
- Smart Round 1: CTR 4.86% (26/535) — no conflicts
- Process runs continuously after Round 1 CTR verification
