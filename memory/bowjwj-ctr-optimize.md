---
name: bowjwj-ctr-optimize
description: Iron rules for CTR-based copy optimization — CTR<3% trigger copy rewrite, CTR=0% immediate stop, CTR<1% auto-optimize
type: feedback
originSessionId: 6f159784-8279-4efa-b7e9-aea4cf509104
---
CTR<3% triggers immediate copy optimization. CTR=0% immediate stop. CTR<1% auto-optimize. 

**Why:** Round 1 (2026-05-01) proved G1=5.7% and G4 (yo家 channels) needs monitoring. Every template below 3% wastes money (~42 PHP/pack minimum). CTR<3% is the new floor — don't just abandon direction, optimize first.

**How to apply:**
- CTR<3%: Immediately trigger copy rewrite for that template/direction. Generate 3 variants: (1) more casual Taglish opener, (2) different emotional angle, (3) shorter/more suspenseful. Deploy best-scored variant.
- CTR=0%: Stop all packs for that template immediately. Check 垃圾词, Taglish mix, shortlink domain health, channel status. Rewrite copy. Mark old template CTR_ZERO_DEPRECATED.
- CTR<1%: Auto-generate optimized variant (more casual Taglish, conversational opener like "i-check mo na" or "uy napansin ko lang"). Deploy within same batch cycle.
- Monitor for 2 consecutive CTR<3% across different copies → escalate to channel health check + shortlink domain blacklist check.
- All CTR measurements use replay-dashboard (PH IP filtered), NOT shortlink visits raw data.
