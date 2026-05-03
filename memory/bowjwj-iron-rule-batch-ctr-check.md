---
name: bowjwj-iron-rule-batch-ctr-check
description: Iron rule — every batch send MUST be followed by a CTR check within 5 minutes, no exceptions
type: feedback
originSessionId: 2ddad364-7211-4fa8-a854-f4bb42aa0b03
---
## 铁律: 每批次发信后必须检查 CTR (2026-05-02 Willy 拍板)

**每一个批次发送后，必须在5分钟内检查该批次的CTR，不允许跳过。**

### 执行规则

1. **每批必查**: 发完一个batch → 等90秒 → 查CTR → 记录 → 再发下一批
2. **查什么**: `replay-dashboard/batches/{batchId}` → `headline.traffic.{clicks, rawClicks, ctr}` + `headline.conversion.{registrations, ftdCount}`
3. **记录**: 每批CTR写入 `stats.db` 或 `events.jsonl`，确保可追溯
4. **不跳过**: 即使是深夜、即使上一批CTR正常，也不能跳过任何一批

### 触发后续动作

| 该批CTR | 动作 |
|---------|------|
| CTR = 0% | 停发 + 检查rawClicks + 换通道/域名 + 优化文案 |
| CTR < 2% | 立即优化文案 + 记录到suspect队列 |
| CTR < 3% | 预警标记，连续2批<3%触发优化 |
| CTR >= 3% | 正常，继续下一批 |

**Why:** 2026-05-01多批次CTR=0%未被及时发现，浪费号码和通道成本。每批必查是最低成本的止损手段。

**How to apply:** 发送循环中，每批send之后立即sleep(90)等数据回流，然后调replay-dashboard API查CTR。CTR值和rawClicks都要记录。
