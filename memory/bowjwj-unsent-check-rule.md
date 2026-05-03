---
name: bowjwj-unsent-check-rule
description: Iron rule — periodically check campaign management for unsent campaigns and click send
type: feedback
originSessionId: 13245daf-357a-446e-8ccb-d8226bbc7b0f
---
## 铁律：定期检查计划管理中未发出的campaign

**每轮发送后或每隔5分钟**，检查是否存在创建但未发出的campaign（launchStatus=scheduled/draft 但实际未投递），手动触发发送。

**Why:** 2026-05-02 发现部分campaign创建后停留在scheduled状态，未真正进入SMPP队列。需要进入计划管理页面检查并点击发送。

**How to apply:**
1. `GET /api/campaigns?pageSize=50` 检查最近创建的campaign
2. 筛选 launchStatus=scheduled 或 status=pending 的campaign
3. 对未发出的campaign，点击前端「发送」按钮或调API触发发送
4. 记录到events.jsonl
