---
name: bowjwj-alert-manager
description: bowjwj 告警管理协调器。Willy 说"告警"、"有啥异常"、"巡检报警"、"查看告警历史"时加载。也可被其他 skill 调用 raise_alert。聚合所有 skill 的红黄告警, 去重/降频, 投递到 TG (高优) 或 events.jsonl (中低优)。薄协调 + 极小落库。
---

# bowjwj-alert-manager (协调器)

## 何时触发

**查询**:
- "看告警" / "有啥异常"
- "告警历史"
- "未处理告警"

**主动 raise** (被其他 skill 调):
- channel-health 扫出 🔴 通道挂
- pack-health 采购预警红
- frozen-manager suspect >= 5
- conversion-funnel 负 ROI 持续
- JWT 7 天过期
- operations-report 拉不到数据

**处理**:
- "标记 #ALERT-X 已处理"
- "忽略这个告警" / "静默 XX 小时"

## 协调目标

集中式告警中心. 薄协调器 + 本地 DB 表. 去重 + 降频 + 投递.

## 告警等级

| 级别 | 定义 | 投递 |
|------|------|------|
| 🔴 P0 | 立即影响发送 (通道全挂 / 预算崩 / 数据丢失) | TG 立即 + 晨报首条 |
| 🟠 P1 | 24h 内必须处理 (库存红 / 负 ROI 大量 / 大批通道黄) | TG 合并批 + 晨报 |
| 🟡 P2 | 本周处理 (小通道黄 / 库存黄 / 模板衰减) | 晨报汇总 |
| 🟢 P3 | 观察级 (新 suspect / 趋势改变) | events.jsonl |

## 数据表 (本地)

```
CREATE TABLE IF NOT EXISTS alerts(
  id INTEGER PRIMARY KEY,
  raised_at TEXT DEFAULT CURRENT_TIMESTAMP,
  source_skill TEXT,           -- 谁 raise 的 (channel-health / ...)
  category TEXT,                 -- channel / pack / campaign / budget / system
  severity TEXT,                 -- P0 / P1 / P2 / P3
  title TEXT,                    -- 短描述
  detail TEXT,                   -- 完整描述 (JSON)
  entity_id TEXT,                -- 关联 id (ch_id / seq / pack_id)
  status TEXT DEFAULT 'open',   -- open / ack / resolved / silenced
  silenced_until TEXT,           -- 静默到某时刻
  delivered_channels TEXT,       -- JSON [tg / console / events]
  resolved_at TEXT,
  fingerprint TEXT UNIQUE        -- 去重指纹 (source+category+entity+title hash)
);
```

## 核心规则

### 1) 去重 (fingerprint)

```
fingerprint = hash(source_skill + category + entity_id + title_normalized)
同 fingerprint 24h 内只告 1 次
超过 24h 同问题再告视作 "恶化"
```

### 2) 降频 (silenced_until)

```
Willy "静默 #ALERT-5 6 小时" → silenced_until = now + 6h
silenced_until 未到的 alert 不重复投递
```

### 3) 升级

```
P1 连续 2 次 raise 且超过 6h 未 ack → 升 P0
P2 连续 3 次 raise 且超过 24h 未 ack → 升 P1
```

### 4) 自动解决

```
每次 raise 新告警时, 反向扫 open alerts:
  如果对应 entity 指标恢复了 (通道失败率降回 < 5%), 自动 resolved
  日志 "auto_resolved_on_metric_recovery"
```

## 投递规则

```
P0 TG 立即:
  via send_telegram_alert() (用户要 TG 接入)
  单条 emoji 开头 "🔴 [P0]..."

P1 合并批:
  每 2 小时汇总一次 TG "🟠 [P1] 待处理 N 条..."

P2 晨报:
  进 daily-playbook 的 "今日 3 件事" 

P3 仅落 events.jsonl:
  不打扰, 查询时才显示
```

## raise_alert 接口 (给其他 skill 调)

```
from alert_manager import raise

raise(source="channel-health",
      category="channel",
      severity="P1",
      title="九 LuckyPlay S 24h 失败率 22%",
      entity_id="165b9ca3",
      detail={"failure_rate": 0.22, "total": 8520, "reasons": [...]})

→ 内部: 计算 fingerprint, 查表去重, 决定是否投递
→ 返回: alert_id + was_delivered
```

## 视图命令

### 1) "看告警"

```
列 open 告警, 按 severity + raised_at 排

🔴 P0 (0 条)
🟠 P1 (2 条):
  #47  2h 前  channel  九 LuckyPlay S 失败率 22%  [ack] [silence 6h]
  #46  4h 前  pack     Smart 库存 < 1 周           [ack]
🟡 P2 (8 条):
  #45  ...
🟢 P3 (last 24h 15 条, 默认折叠)
```

### 2) "告警历史"

```
GET alerts ORDER BY raised_at DESC LIMIT 50
含已 resolved 的, 支持筛 status/severity
```

### 3) 处理命令

```
"ack #47"      → status = ack
"resolve #47"  → status = resolved, resolved_at = now
"silence #47 6h" → silenced_until = now + 6h
"忽略 #47"     → 同 silence 24h
```

## TG 投递实现 (需要 Willy 先配)

```
需要:
  1. TG bot token (后台已有 tg_bot adapter)
  2. Willy 的 TG user id 6694261813 (已知)
  3. 本 skill 调 TG send 接口

方法 1 (走后台): 
  后台本身有 tg_bot adapter, 探源码是否有 send_custom_message API
  
方法 2 (我自建):
  直接调 https://api.telegram.org/bot<token>/sendMessage
  token 可从 bowjwj 后台 adapter config 读 (解密)
  chat_id = 6694261813

优先方法 2, 但 token 要 Willy 手动给.
  (1Password 存或本地文件, 类似 .jwt)
```

## 与其他 skill 边界

```
所有 skill 发现异常 → 调 raise_alert (本 skill)
本 skill 决定:
  1. 要不要立即告 (去重 + 降频)
  2. 投递哪个 channel (TG/events)
  3. 升级/解决时机

daily-playbook 晨报会从本 skill 读 P2 清单
frozen-manager 只建议冻结, 不告警, 由本 skill 转 alert
```

## 已知坑

1. **TG 可能被限速**: 大批 P0 风暴时 TG rate limit 429, 要退避重试
2. **fingerprint 太严格**: 同通道不同 entity 同 title 视为不同, 可能刷屏
3. **自动解决过激**: 指标回到阈值瞬间就 resolve, 可能本质没解决只是瞬时好. 保守: 恢复 >1h 才 resolve
4. **silenced_until 过期**: 到时 auto re-open 还是保持 silenced 状态? 选 re-open
5. **晨报/晚报**: daily-playbook 读时要 filter 已 ack 的
6. **TG 投递失败**: 要本地事件兜底, 不能丢

## 红线

- 不自动处理告警 (除自动 resolved)
- 不自动改系统配置
- 不发大批 P0 (每 5min 最多 3 条 P0)
- 不跨用户 (只 Willy)
- TG token 不硬编码, 必须从 1P / .jwt 式文件读

## 依赖 skills

```
所有 skill 都可能调 raise_alert
bowjwj-daily-playbook 读 P2 清单
```
