---
name: bowjwj-highest-ftd-copy
description: Iron rule: use last 3 days' highest FTD/conversion copy as the only template for today's sends
type: feedback
originSessionId: 475654df-8077-45b9-ab85-432d0554891d
---
Iron rule: each day, use ONLY the copy/template that had the highest FTD (first-time deposit / conversion) from the last 3 days. No rotation unless that copy drops below CTR threshold.

**Why:** Willy wants to maximize conversion — the copy that drove the most real deposits over the last 3 days is the most proven. 3-day window avoids single-day fluctuation noise. Rotating dilutes results.

**How to apply:** At start of each day's sending, query last 3 days' copy performance (dateFrom = 3 days ago), pick the single highest-FTD copy, set it as the ONLY template in rotation for both Globe and Smart. Only switch if CTR drops below 3% or Willy says otherwise.
