---
name: bowjwj-best-deposit-copy
description: Iron rule — daily sending must use last 3 days' highest deposit/conversion copy
type: feedback
originSessionId: 53779ebb-debe-49b2-8855-ee9af94d7ff1
---
# 铁律: 每次发送只用最近3天转化充值最高的文案 (2026-05-03 Willy拍板)

**Rule**: 不轮训多条文案。每天查最近3天FTD+deposit最高的那一条，集中放量。

**当前最佳 (2026-05-03)**:
- 文案: W1 = "may P5,288 na pumasok sa account mo, check mo na bago mag-midnight ${shortUrl}"
- Globe模板ID: `6c6beb8e-8f68-4961-953a-09dca33d4a7b`
- Smart模板ID: `ef7bf1da-5e3e-4076-be8b-213a604f7796`
- 近3天(May 1-3): 221FTD / 229617deposit (5.8x碾压第2名, 675批次, 982k发送量)

**Why**: 3天数据验证W1远超其他文案，轮训稀释效果。集中放量最优文案才是正确策略。

**How to apply**:
- GLOBE_TPL 和 SMART_TPL 各只含W1一条
- 每天09:00 BJT查最近3天operations-report
- 如有新文案超过W1，需Willy点头后切换
- 无数据回退到W1
