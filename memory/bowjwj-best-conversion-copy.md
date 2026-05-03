---
name: bowjwj-best-conversion-copy
description: Iron rule: daily sending MUST use copy with highest 3-day deposit/conversion
type: feedback
originSessionId: 6efd104b-f321-458e-ab64-31763009c0bd
---
## Iron rule: 最近3天转化充值最高的文案优先发送

**Why**: 转化充值 (FTD/deposit) 是最终变现指标，CTR高不一定转化好。只发最近3天内转化充值最高的文案，确保每条短信最大化变现。

**How to apply**:
1. 每次发信前，查询最近3天的 operations-report / replay-dashboard 数据
2. 按 deposit 金额或 FTD 数量降序排列文案
3. 选 Top 1 文案作为当轮发信文案
4. Globe/Dito 和 Smart/TNT 分开排名，各自用各自的 Top 文案
5. 如果最近3天无转化数据（新文案），回退到 CTR 最高的文案
6. 每24小时重新排名一次，自动切换
