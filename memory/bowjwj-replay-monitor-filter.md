---
name: bowjwj-replay-monitor-filter
description: 铁律: 复盘监控API用createdByUserId+windowPreset=24H直接过滤凯总，无需客户端二次过滤
type: project
originSessionId: cc992e84-bc0e-4e0c-9fbf-9e0ea97ff264
---
**铁律**: API参数用 `createdByUserId=750e89c7-e91f-46df-bae5-42109c0deb82` + `windowPreset=24H`，直接过滤凯总【巴西】。

**Why**: 旧参数 `creator=` + `w=24H` 不生效(返回windowPreset=72H)，且creator参数不完整过滤混入小财财。正确参数组合后API直接返回纯凯总数据，无需客户端过滤。

**How to apply**: 
- API: `GET /api/replay-dashboard/batches?createdByUserId=750e89c7-e91f-46df-bae5-42109c0deb82&page=5&pageSize=10&windowPreset=24H`
- page=5 和 page=6 各10条 = 20条凯总专属
- 不要用 `creator=` 或 `w=` 参数
