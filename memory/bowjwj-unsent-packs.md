---
name: bowjwj-unsent-packs
description: Iron rule — check plan management for unlaunched/unsent campaigns and manually click to send unsent packs before starting new rounds
type: feedback
originSessionId: 05bef769-7f62-4a5e-ac3a-4427eeea3462
---
## 铁律：发送前检查未发计划

每轮发送前/重启前，必须进入计划管理检查：

1. **检查未发送的 campaigns** — 查询状态为 `created` 但未 `launched` 的计划
2. **点击未发出去的包** — 对未发送的包手动触发 `send` API
3. **避免包浪费** — 已分配但未发送的包会一直被占用，必须处理掉

**Why:** 包被分配给 campaign 后如果不发送，会一直处于 `PHONE_PACK_ALREADY_ASSIGNED` 状态，后续无法使用。每轮发送前先清理未发计划，确保号码包不浪费。

**How to apply:** 每轮发送前/进程重启前 → 查 DB `campaigns WHERE launch_status='created'` → 逐个 launch + send
