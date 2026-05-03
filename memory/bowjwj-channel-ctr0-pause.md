---
name: bowjwj-channel-ctr0-pause
description: Iron rule: single channel with multiple CTR=0% sends → pause channel + ask Willy to decide
type: feedback
originSessionId: 90be422a-8814-4457-816b-eab01a15d95f
---
## 铁律: 单通道多次CTR=0%暂停 (2026-05-03)

**单个通道连续多次发送CTR=0% → 立即暂停该通道，告诉Willy由他决策是否继续使用。**

### 触发条件
- 同一通道连续2次发送CTR=0% → 触发

### 执行动作
1. 立即暂停该通道（加入blockedChannels / PERMA_BLOCKED）
2. 通知Willy：通道名 + CTR=0次数 + 建议（继续用/换通道/检查短链）

### 决策权
- **Willy决策**是否继续使用该通道
- 不可自动解封

**Why:** CTR=0%=发送全浪费钱，连续多次=通道可能被运营商风控或短链被拉黑。暂停比继续发更安全。

**How to apply:**
- 每轮发送后T+60s检查CTR
- 同通道连续2次CTR=0% → 暂停 + AskUserQuestion问Willy
- Willy说继续用 → 解封继续
- Willy说换 → 永久封禁
