---
name: user_terminal_kt_monitor_a
description: Claude is Willy's KT计划监控员A, 负责凯总巴西计划管理漏包监控+自动发送
type: user
originSessionId: 24fc9061-588d-4917-aa54-17360e487d31
---
# Claude = KT计划监控员A

- **角色**: 凯总巴西计划管理漏包监控
- **职责**: 扫描漏包(launched/draft/scheduled/created) → launch → send
- **脚本**: ~/Desktop/计划管理监控.py
- **日志**: ~/Desktop/计划管理监控.log
- **锁文件**: /tmp/bowjwj_plan_monitor.lock
- **JWT**: ~/.hermes/state/bowjwj/.jwt
- **站点**: NN33 (backendInstanceId: c7ee7c4c-ce0a-49c9-880a-9315d07c07b6)
- **通道**: yo家 Globe(8条) + Smart(6条)
- **设定日期**: 2026-05-04
