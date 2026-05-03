---
name: bowjwj-race-refresh-not-grab
description: Iron rule: on pack conflict (RACE), refresh current page instead of grabbing different packs
type: feedback
originSessionId: 6efd104b-f321-458e-ab64-31763009c0bd
---
## 铁律: 包源冲突 → 刷新当前页, 不跳轮不抢包

**Why**: 凯总巴西项目与我们的发送共享同一号码包池 (凯特ai发送：银河v数据4月)。当出现 PHONE_PACK_ALREADY_ASSIGNED 冲突时, 跳去其他页面抢包会导致双方踩踏。正确做法是刷新当前页面重新获取可用包列表, 已分配的包已被 API 过滤掉, 新查询返回剩余可用包。

**How to apply**:
1. POST campaign 返回 "已分配给计划" 错误 → 判定 RACE
2. 将冲突包标记为 pack_used (避免再次选中)
3. 等待 3s 后重新调用同一 page/pageSize 的 GET /api/phone-packs
4. 用刷新后的新包列表重试 POST campaign
5. 连续 3 次 RACE 等待 30s 后继续刷新 (不跳轮)
6. 永远不要因为 RACE 跳到其他页码或换 carrier
