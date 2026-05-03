---
name: bowjwj-pack-page-current
description: Iron rule — ONLY fetch from page 7, locked to kt06 terminal, other terminals cannot modify
type: feedback
originSessionId: dfcf31d8-ba08-4b1f-86ef-d9e8babcc757
---

## 铁律: kt06终端独占 page 7，其他终端禁止修改 (2026-05-03)

**Why:** 凯总巴西 campaign 抢占号码包，固定在 page 7 获取包源避免冲突。只有kt06终端有权修改此配置。

**How to apply:**
- PACK_PAGE 必须 = 7
- API: `GET /api/phone-packs?q=凯特ai发送&page=7&pageSize=20&backendInstanceId={BID}`
- 冲突时刷新当前页面 (page 7)，不跳页
- 其他终端禁止修改 PACK_PAGE
- 这是铁律，不可修改
