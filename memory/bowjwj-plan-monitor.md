---
name: bowjwj-plan-monitor
description: 凯总巴西计划管理漏包监控 — 每5min自动扫描+发送, 锁文件防重叠
type: project
originSessionId: 90be422a-8814-4457-816b-eab01a15d95f
---

## 计划管理监控 (2026-05-03)

- **频率**: 每 5 分钟 (cron: `*/5 * * * *`)
- **脚本**: `/Users/kate/Desktop/计划管理监控.py`
- **日志**: `/Users/kate/Desktop/计划管理监控.log`
- **锁文件**: `/tmp/bowjwj_plan_monitor.lock`

### 监控规则

- **目标**: 凯总巴西 (campaignId 含 "凯总")
- **漏包定义**: launchStatus = launched / draft / scheduled / created
- **发送流程**: 
  - launched → 直接 POST /send
  - draft/created/scheduled → POST /launch → POST /send
- **通道**: Globe/Dito→yo家Globe(8条), Smart/TNT→yo家Smart(6条)
- **间隔**: 0.5s/条
- **防重叠**: 文件锁 `/tmp/bowjwj_plan_monitor.lock`

### 当前状态 (2026-05-03)

- 今日已发送: 总计约 824+ 凯总巴西漏包 (443G + 381S)
- 凯总巴西持续创建新campaign, 需要持续监控
- PATCH API不支持 (404), 文案通过创建时预设
