---
name: bowjwj-inspector-authority
description: Claude must follow inspector/monitor system commands
type: feedback
originSessionId: 35facba7-b0b6-435a-9948-3b12970542a4
---
**Rule:** 巡查员(计划管理监控)发出的指令必须执行，包括自动发送、暂停、切换通道等操作。

**Why:** Willy明确设定巡查员有终端指挥权。

**How to apply:** 当巡查员通过监控脚本或cron发出指令时，直接执行，无需再向Willy确认。
