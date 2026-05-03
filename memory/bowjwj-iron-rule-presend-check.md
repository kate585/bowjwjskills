---
name: bowjwj-iron-rule-presend-check
description: Iron rule — before each send round, check AICRM dashboard for unsent campaigns and manually click send
type: feedback
originSessionId: 6365c4e8-fc05-4de5-8f5d-ed75b46595a1
---
## 铁律: 发信前检查未发送的 campaign

**每轮发信前**必须检查 AICRM dashboard 是否有创建了但未发出的 campaign (status="created")，**手动点击发送**。

**Why:** 2026-05-02 发现 48 个 campaign 在 DB 中 status="created" 但从未 launch。其中 25 个通过 API 补发成功，23 个因为 GG家全网通通道被跳过。这些包已分配号码但没发出去 = 浪费号码资源。

**How to apply:**
1. 每轮发信前，检查 DB: `SELECT id FROM campaigns WHERE status='created'`
2. 对未发出的 campaign，调用 `POST /api/campaigns/{id}/launch`
3. 跳过 GG家全网通通道的 campaign
4. 记录 launch 结果
