---
name: bowjwj-channel-failover
description: Channel failover rule — when a channel returns 504/error, immediately switch to backup channel
type: feedback
originSessionId: 6f159784-8279-4efa-b7e9-aea4cf509104
---

When a channel returns consecutive 504 errors or no_sessions, immediately switch to next available channel in the same carrier pool (Globe/Smart).

**2026-05-02:** GG全家网 UNBANNED — Willy 主动要求用 GG 全网通 3 通道 (AAA/Bbb/BBB2) 发送。当前为主力通道池。

**2026-05-01:** All 3 GG全网通 channels enabled: MP Time, MPBonus, and 旧GG全网通 (previously banned, now re-enabled by Willy). All are all-carrier, added to BOTH Smart and Globe pools.

**How to apply:**
- If 2 consecutive rounds return no_sessions (504), stop and switch to next available channel in same carrier pool
- GG全家网 现在是主力通道，已解除 ban
- Don't wait for manual intervention — auto-switch within the same send session
- Log the channel switch event for post-mortem
