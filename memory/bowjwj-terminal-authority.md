---
name: bowjwj-terminal-authority
description: Iron rule — only current terminal (kt09) can modify auto_send.py, other terminals read-only
type: feedback
originSessionId: 475654df-8077-45b9-ab85-432d0554891d
---
# 铁律: 只允许本终端修改配置 (2026-05-03 Willy)

**Rule**: auto_send.py 只允许本终端 (kt09) 修改，其他终端禁止修改，只能读取。

**Why**: 多终端同时修改导致 packPage 在 2→3→4→5→6→8→10 之间反复跳变，发送循环用错页面。

**How to apply**:
- 本终端修改 auto_send.py 前确认没有其他终端在编辑
- 其他终端需要改配置→通知 Willy→由本终端执行
- 禁止其他终端修改 PACK_PAGE / Q / carriers 配置
