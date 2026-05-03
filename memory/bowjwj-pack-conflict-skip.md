---
name: bowjwj-pack-conflict-skip
description: Iron rule: pack conflict → refresh current API page, re-fetch fresh packs, NEVER fight for same packs
type: feedback
originSessionId: 91d8a843-b2aa-48d6-bf7e-fb3fdf8a4bc4
---

Iron rule: when pack conflict (PHONE_PACK_ALREADY_ASSIGNED / "已分配给计划" / contaminated page):

**fetch_packs level**: When a page returns >0 contaminated packs (already used or assigned) and <5 fresh packs, refresh the SAME page (up to 3 retries with 1.5s wait). Don't jump to next page — the API may reassign packs between refreshes.

**Main loop level**: `result == "race"` → mark packs used → continue to next round (new round re-calls fetch_packs for fresh packs).

**Why:** 2026-05-03 Willy指定 — 出现包源冲突时在当前页面刷新重新取包，而不是去抢包。同页面API可能重新分配新包。重试同样的包ID = 浪费资源 + 跟凯总巴西抢包。

**How to apply:** fetch_packs inner refresh loop: `if contaminated > 0 and fresh < 5 and refresh < 2: time.sleep(1.5); continue`
