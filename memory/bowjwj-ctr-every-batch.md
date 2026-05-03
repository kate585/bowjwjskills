---
name: bowjwj-ctr-every-batch
description: Iron rule — every batch sent MUST have CTR checked, no batch skipped
type: feedback
---

## 铁律：发送的每一个批次必须检查CTR

**每一个批次发送后，必须在 T+60s 内查询 replay-dashboard CTR，不得跳过任何批次。每批次CTR记录到 stats.db。**

**Why:** 2026-05-02 发现部分批次发完但CTR=0%，未及时发现和处理。

**How to apply:**
1. CTR monitor 必须处理每一个 `monitored_campaigns` 中的批次
2. MONITOR_DELAY=60s，到达后立即查询
3. 每批次CTR记录到 stats.db
4. CTR=0% → 立即切换通道+换文案
5. RECAP 每15s显示"待CTR批次数量"
