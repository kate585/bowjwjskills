---
name: bowjwj-pack-page-current
description: Iron rule — ONLY fetch packs from current configured page, refresh on conflict, never fight for packs
type: feedback
originSessionId: dfcf31d8-ba08-4b1f-86ef-d9e8babcc757
---

## 铁律: 固定页面获取包源，冲突时刷新当前页面，不抢包 (2026-05-03)

**Why:** 凯总巴西 campaign 抢占大量号码包导致 PHONE_PACK_ALREADY_ASSIGNED 冲突。固定在当前配置页面获取包源，冲突时刷新同一页面拿最新排列，绝不跳到其他页面抢包。

**How to apply:**
- 使用 send_rules.json 中配置的 packPage + searchQuery
- API: `GET /api/phone-packs?q={searchQuery}&page={packPage}&pageSize=20&backendInstanceId={BID}`
- 出现 PHONE_PACK_ALREADY_ASSIGNED → 刷新当前页面（force-refresh prereq）
- 绝不跳到其他页面抢包
- sourceMustStartWith 必须匹配实际 pack source 前缀（如 "凯特ai发送"）
- 这是铁律，不可修改
