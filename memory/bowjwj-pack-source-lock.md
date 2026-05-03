---
name: bowjwj-pack-source-lock
description: 铁律：固定"凯特ai发送：银河v数据4月"第5页，冲突只刷新不跳页不换源
type: feedback
originSessionId: 91d8a843-b2aa-48d6-bf7e-fb3fdf8a4bc4
---
# 铁律: 固定页面刷新，不抢包不跳源 (2026-05-03 Willy)

**Rule**: 号码包永远固定 searchQuery="凯特ai发送" + page=2-5循环 + pageSize=20。出现 PHONE_PACK_ALREADY_ASSIGNED 时只刷新当前页(调用 fetch_prereq)，绝不跳页、不换源、不改 pageSize。

**Why**: 跳页=和其他终端抢包，互相踩踏。各自固定页面独立，冲突只在当前页重新拉取等释放。

**How to apply**:
- send_rules.json 固定: searchQuery="凯特ai发送：银河v数据4月", packPage=2-5循环, packPageSize=20
- sourceMustStartWith="凯特ai发送：银河v数据4月" 客户端双重过滤
- globe/smart carriers 同范围: packPage=2-5循环
- 冲突处理: 黑名单300s → 清used_pack_ids → fetch_prereq(同页同源同size) → 5s后重试
- 禁止: 动态换页、增大pageSize、切换searchQuery、切换source、random page
