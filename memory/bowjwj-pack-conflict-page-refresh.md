---
name: bowjwj-pack-conflict-page-refresh
description: Iron rule — when pack source conflict occurs, refresh current page, never grab packs from other pages
type: feedback
originSessionId: 475654df-8077-45b9-ab85-432d0554891d
---
# 铁律: 包源冲突时刷新当前页，不抢包 (2026-05-03 Willy)

**Rule**: 出现包源冲突(PHONE_PACK_ALREADY_ASSIGNED等)时，必须在当前页面刷新获取新包，禁止跳到其他页面抢包。

**Why**: 抢包会导致多终端包源混乱，凯总巴西项目包碰撞，归因碎片化。固定page=5+搜索词"凯特ai发送：银河v数据4月"，当前页的包用完了就刷新等新包，不去其他页。

**How to apply**:
- 冲突发生时: 重新GET同page同q参数，不改变page number
- 禁止: 冲突后page++、随机换页、切其他搜索词
- 当前页全冲突→等cooldown后刷新同页
- 修改send_rules.json的packPage必须Willy点头
