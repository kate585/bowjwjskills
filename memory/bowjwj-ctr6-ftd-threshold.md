---
name: bowjwj-ctr6-ftd-threshold
description: Iron rule: 6% CTR + FTD双门槛，高CTR无首存淘汰
type: feedback
originSessionId: 90be422a-8814-4457-816b-eab01a15d95f
---

## 铁律: 文案必须同时满足 6% CTR + 首存双重门槛 (2026-05-03)

**Rule**: 每条文案必须达成两个条件才能保留:
1. **CTR ≥ 6%** (新目标，从5%提升)
2. **必须有FTD** (首存转化)

**淘汰规则**:
- CTR高但FTD=0 → 淘汰 (虚假繁荣，用户来了不充钱)
- CTR<6%但FTD>0 → 优化文案提升CTR
- CTR<6%且FTD=0 → 立即淘汰
- CTR≥6%且FTD>0 → ✅ 优质文案，集中放量

**Why**: CTR高≠变现好。有些文案吸引点击但用户不充值，白白浪费短信成本。必须CTR+FTD双高才算优质。

**How to apply**:
- 每次复盘先按CTR≥6%筛选，再按FTD降序排列
- 只有通过双门槛的文案才能进入发送池
- W1已验证: 221FTD/₱229K deposit，待技术修复后验证CTR
- 新文案上线后T+30分钟查CTR和FTD，不达标立即淘汰

**当前状态 (2026-05-03 20:42)**:
- 复盘看板技术修复中，暂时无法查询per-copy CTR和FTD
- 已确认W1为最高FTD文案 (221FTD)
- 修复后优先验证: W1 CTR是否≥6%，14条Willy文案各自CTR和FTD
