---
name: bowjwj-pack-page-11-12-kt04
description: 铁律: kt04终端永久固定第11-12页，任何情况下不得更改
type: feedback
originSessionId: 475654df-8077-45b9-ab85-432d0554891d
---
# 铁律: kt04终端固定page=11-12 (2026-05-03 Willy)

**Rule**: kt04终端固定获取包源在第11-12页，两页合并取包，任何情况下不得更改。

**Why**: 多终端同时修改导致 packPage 反复跳变，发送循环用错页面。kt02=6-8, kt04=11-12 各锁定各自页面。

**How to apply**:
- kt04 本终端修改 fast_send_kt08.py 前确认没有其他终端在编辑
- 其他终端禁止修改 kt04 的 page 配置
- pack_pages = [11, 12] 铁律不可改
