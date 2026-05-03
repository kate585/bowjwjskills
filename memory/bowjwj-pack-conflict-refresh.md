---
name: bowjwj-pack-conflict-refresh
description: Iron rule: pack conflict → refresh same page, never grab other packs
type: feedback
originSessionId: 8ce496fa-bda4-4f48-bc14-023004c0280d
---
## 包源冲突铁律

**Why:** Willy 2026-05-03 明确 — 出现 PHONE_PACK_ALREADY_ASSIGNED 包源冲突时，在当前页面刷新重新取包，不去抢其他页/其他源的包。

**How to apply:**
1. 遇到 `PHONE_PACK_ALREADY_ASSIGNED` → 在当前 page 重新 GET 同一 URL
2. 绝不切换到其他 page、其他 source、其他 search query
3. 同一页面 shuffle 后重新选包即可
4. 如果当前页面所有包都被占 → 等 cooldown 后刷新同一页面再试
5. 绝不跨页抢包 — 那是凯总巴西的地盘
