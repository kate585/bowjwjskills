---
name: bowjwj-ctr-per-batch-5pct
description: Iron rule — check CTR per individual batch, require ≥5%, do NOT use average CTR across batches
type: feedback
originSessionId: 13245daf-357a-446e-8ccb-d8226bbc7b0f
---
## 铁律：按每个发送批次独立查看CTR，不低于5%

**每个批次单独计算CTR，不计算全局均CTR。** 单个批次CTR < 5% 立即触发优化。

**Why:** 2026-05-02 用户明确要求不用平均CTR来评判，每个批次独立评估。平均CTR会掩盖差批次 — 3个10% + 1个1% = 均7.75%看起来OK，但1%那个批次其实完全浪费了。

**How to apply:**
1. 每批次发完后单独查CTR
2. CTR ≥ 5%: 该批次OK，继续
3. CTR < 5%: 该批次立即触发文案/通道优化
4. CTR = 0%: 该批次立即停发，切通道+换文案
5. 不计算"当前平均CTR"来做决策 — 只看单批次
