---
name: bowjwj-pending-campaign-channel-retry
description: Iron rule: scan launched-but-unsent campaigns every minute, retry via alternative channels
type: feedback
originSessionId: 90be422a-8814-4457-816b-eab01a15d95f
---

## 铁律: 每分钟扫描已启动待发送campaign，换通道重发 (2026-05-03)

**Rule**: 每分钟扫描所有已启动(launched)但处于pending/sending状态的campaign，进入详情检查发送状态，对未发送成功的包选择其他同运营商通道重新发送。

**触发条件**:
- campaign status = launched/pending/sending
- send-log显示 sentCount=0 或 successCount远低于targetCount
- 连续2分钟同一campaign仍待发送 → 触发换通道

**执行流程**:
1. GET /api/campaigns?backendInstanceId=NN33&status=pending&launchStatus=sending
2. 对每个campaign检查 send-log 发送进度
3. 如果 sentCount=0 或发送率<50%:
   - 切换到同运营商其他通道
   - POST /api/campaigns/{id}/send 使用新通道
4. 如果所有同运营商通道都失败 → 通知Willly

**Why**: 之前发现大量campaign创建并启动后实际sent=0（batch replay数据显示全零），消息卡在"已启动待发送"状态未真正发出。主动扫描+换通道可避免消息积压。

**How to apply**:
- 每分钟执行一次扫描
- 只处理最近30分钟内创建的campaign（避免重复处理旧campaign）
- 换通道时优先选择同运营商中CTR表现最好的通道
- 每个campaign最多换3次通道，3次后放弃并通知

**当前状态 (2026-05-03 20:52)**:
- 所有终端已停发，暂无新campaign产生
- 待技术恢复后部署此自动扫描逻辑
