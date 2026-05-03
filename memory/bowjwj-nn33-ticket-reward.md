---
name: bowjwj-nn33-ticket-reward
description: NN33 ticket reward: ALL templates use FREE_SPIN 2804039 "SMS Super Ace Free CouponX", changed from RAFFLE 2659055 on 2026-05-02
type: feedback
originSessionId: 990b58bd-91fe-4fd4-9f44-437afc3a6d8e
---
## NN33 票劵奖励 (2026-05-02 更新)

**铁律**: NN33 所有模板的 ticketRewards 统一使用:
- ticketType: `FREE_SPIN`
- ticketId: `2804039`
- ticketQuantity: 1
- Name: "SMS Super Ace Free CouponX"

**已更新**: 4761+ 个模板已通过 PATCH `/api/campaign-templates/{id}` 批量更新完毕。

**Why:** Willy 指定将所有 NN33 模板从 RAFFLE 2659055 (幸运红包 SMS NN33VIP) 改为 FREE_SPIN 2804039 (SMS Super Ace Free CouponX)。

**How to apply:**
- PATCH `/api/campaign-templates/{id}` body: `{"ticketRewards": [{"ticketType": "FREE_SPIN", "ticketId": "2804039", "ticketQuantity": 1}]}`
- 需 backendInstanceId header: `c7ee7c4c-ce0a-49c9-880a-9315d07c07b6`
- 注意: AI 自动模板创建时默认可能仍是 RAFFLE:2804039，需定期巡检修正 ticketType
