---
name: bowjwj-plan-check-unsent
description: Iron rule — after creating+launching campaigns, check plan management for unsent packs and trigger sending. Pack-level verification.
type: feedback
originSessionId: 1372c69c-cc4c-4aa0-929e-02360f506c51
---
## 铁律: 发信后检查未发包 (2026-05-02)

**每轮发信后必须进入计划管理检查:**
1. 检查 launched 但 status!=sent 的 campaign
2. 逐包检查是否已发送
3. 未发包立即触发 `POST /api/campaigns/{id}/send` 发送

**Why:** 2026-05-02 发现 36053 campaigns 中有 8 个 launched 但未发送。创建+启动后若不检查，号码包闲置浪费，代理线占着不发。

**How to apply:**
- 每轮 send_round 结束后，检查本轮创建的所有 campaign
- 验证每个 campaign 的每个 pack 都有对应的 send 记录
- 未发送的 pack 立即补发
- 已删除/孤儿 campaign (API 返回 404) 跳过并记录
