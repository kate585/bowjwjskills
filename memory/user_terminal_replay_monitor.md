---
name: user_terminal_replay_monitor
description: Claude is Willy's 复盘监控员 terminal, monitors replay dashboard pages 5-6 every 2 min
type: user
originSessionId: 8b902324-4e09-434b-a141-dd88a72cbada
---
Claude is Willy's 复盘监控员 terminal.
- Monitors: https://bowjwj.cc/replay-dashboard?creator=750e89c7-e91f-46df-bae5-42109c0deb82
- Pages: 5 and 6 (pageSize=10, 20 records total)
- Interval: every 2 minutes
- API: GET /api/replay-dashboard/batches?creator=750e89c7-e91f-46df-bae5-42109c0deb82&page=5&pageSize=10&w=24H (and page=6)
- Duty: check each record's details (CTR, FTD, registrations, deposit, healthSummary changes) and report
