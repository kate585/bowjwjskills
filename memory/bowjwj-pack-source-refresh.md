---
name: bowjwj-pack-source-refresh
description: Iron rule - when pack source conflicts, refresh current page instead of fighting for packs
type: feedback
originSessionId: 53779ebb-debe-49b2-8855-ee9af94d7ff1
---
# 包源冲突时刷新页面，不抢包

**Rule**: 出现包源冲突时，在当前页面刷新 (re-query API) 而不是去和其他终端抢包。

**Why**: 多终端 (001-004) 同时发"凯特ai发送"包，包源冲突是常态。抢包 = 浪费 API 调用 + 创建失败的 campaign。

**How to apply**:
- fetch_packs 返回 <5 包时，先 sleep 5-10s，然后 refresh (重新 query API)，不立即 SKIP
- 最多 refresh 3 次，都失败才真正 SKIP 该轮
- 不在同一页面反复抢已 assigned 的包
