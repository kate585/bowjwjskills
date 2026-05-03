---
name: bowjwj-channel-health
description: bowjwj 通道健康监控协调器。Willy 说"看通道"、"通道排行"、"通道健康"、"通道余额"、"哪个通道好"、"XX 通道咋样"、"通道失败率"时加载。三刀合璧 — adapters/instances 拿配置+余额, intelligence/dimensions 拿全系统 Top, send-logs 拿失败率。只协调, 不自带脚本。
---

# bowjwj-channel-health (协调器)

## 何时触发

**单通道**:
- "看 九 LuckyPlay 通道健康"
- "通道 165b9ca3 咋样"
- "3yo家 余额多少"

**排行 / 巡检**:
- "通道排行" / "Top 10 通道"
- "通道健康" / "通道巡检" (日常扫全 NN33 ph)
- "哪个通道 ROI 最高" / "哪个失败率高"

**告警式**:
- "有通道挂了吗" (configInvalidSince 非空 / balance 低 / 失败率高)
- "加白过期了吗" (某号段被多个通道批量拒)

## 协调目标

薄协调层, 3 个 API 拼视图. 不落库, 实时查, 每次触发都拉最新. 判断逻辑硬编码在 skill.

## 三刀数据源

### 刀 1: `/api/adapters/instances` (配置 + 余额)

```
每条通道字段:
  id / name / type / enabled
  configJson (driver/host/sourceAddr/unitPrice/currency/maxSmsPerSecond)
  configInvalidSince   非 null 表示配置坏了
  balance              余额 (部分通道有, 部分 null)
  backendInstanceIds   绑定的游戏后端

NN33 ph 过滤:
  enabled=true AND type=sms AND BID in backendInstanceIds
  BID = c7ee7c4c-ce0a-49c9-880a-9315d07c07b6
  通常 23 条左右
```

### 刀 2: `/api/intelligence/dimensions?period=7d&backendInstanceId=<BID>` (业绩)

```
dimensions.smsChannel 每条:
  dimensionKey, dimensionLabel, campaignCount
  funnel (target, delivered, deliveryRate, clicked, ctr, 
          registered, registrationRate, ftd, ftdRate)
  cost   (smsCost, costPerDelivered, costPerClick, 
          costPerRegistration, costPerFtd, roi)
  compositeScore, rank, tags, trend
  radar.axes[6], scores

period: 7d / 14d / 30d / custom
全系统聚合, 不是 Willy 个人. 基线用.
```

### 刀 3: `/api/send-logs?adapterInstanceId=<ch_id>` (失败率)

```
每条 send-log:
  status: success / failed
  failureReason

算失败率: failed / (success + failed) 最近 24h
```

## 视图组装 (AI 现场拼)

### 1) 单通道体检 "看 九 LuckyPlay"

```
GET adapters/instances -> 过滤 name 含 "九 LuckyPlay" -> ch_id + config + balance
GET intelligence/dimensions -> smsChannel 按 ch_id 匹配 -> 业绩
GET send-logs?adapterInstanceId=<ch_id>&pageSize=100 -> 算失败率
```

输出模板:
```
📡 九 yo家 LuckyPlay S (165b9ca3)

📋 配置:
  driver:     smpp
  host:       smpp.buzzingga.com:1080
  sourceAddr: LuckyPlay S
  unitPrice:  PHP 0.21 / 条  250 sms/s
  状态:       enabled, 配置有效
  余额:       N/A

📊 近 7 天业绩 (全系统):
  rank 3/21  score 85.2
  CTR 4.32%  注册率 0.88%  FTD 率 5.12%  ROI 0.78
  tags: high_click, high_convert
  trend: stable

🚨 近 24h 送达:
  total 8520  失败率 0.3%  健康

🎯 我的历史: rounds 3  sent 233  click 7  CTR 3.0%

💡 健康通道, 可继续大规模用
```

### 2) 排行 "Top 10 通道"

```
GET intelligence/dimensions
按 compositeScore desc Top 10
表格: rank, name, ctr, reg, ftd, roi, tags, trend
```

### 3) 巡检 "通道健康"

```
扫全 23 条:
  配置坏 (configInvalidSince 非 null)
  低余额 (< 10K PHP 如果有字段)
  高失败率 (> 10%)
  低 ROI (< 0.2)
  低 CTR (< 0.5%)
按严重性列清单, 无告警就 "23 通道全健康"
```

## 判定阈值

| 指标 | 阈值 | 告警 |
|------|------|------|
| configInvalidSince 非 null | - | 红 配置坏 |
| balance < 10K PHP | - | 黄 提醒充值 |
| 24h 失败率 > 20% | - | 红 通道可能挂 |
| 24h 失败率 > 5% | - | 黄 观察 |
| 7d ROI < 0.2 | campaigns >= 10 | 红 亏本 |
| 7d ROI 0.2-0.5 | campaigns >= 10 | 黄 看趋势 |
| 7d CTR < 0.5% | campaigns >= 10 | 红 通道差 |
| 7d deliveryRate < 95% | campaigns >= 10 | 黄 投递不稳 |
| trend=falling | 连续 2 周 | 黄 衰减 |

## 与其他 skill 边界

```
bowjwj-frozen-manager:
  本 skill 产 "红通道告警" -> 建议 frozen_channel
  不自动冻, 输出给 frozen-manager 消化

bowjwj-batch-send:
  发起前 consult 通道黑名单
  绿/黄 -> 允许
  红    -> 警告或 skip

bowjwj-conversion-funnel:
  共用 intelligence/dimensions, 别重拉
```

## 特殊处理

### 加白过期识别

```
信号:
  某通道某号段 (Smart/Globe/DITO) 24h 送达率 < 80%
  其他通道同号段送达率 > 95%
  -> 单通道 x 单号段 "加白过期" 嫌疑
只观察, 不自动冻. Willy 确认后联系上游补白.
```

### 包料通道

```
牛排/小新/龙少/大官人Globe 是包料 (对方给料)
不能用 Willy 自己料子
-> 扫时标 "包料通道, 你料子不能发"
-> batch-send 不允许配自己 pack
```

## 已知坑

1. balance 大多 null, 只 Buzz/白羊 等部分通道有
2. intelligence compositeScore 有 campaignCount 加权, 小样本会异常高
3. deliveryRate 是 intelligence 全系统聚合, send-log 失败率是单通道本地, 不是一回事
4. configInvalidSince 是配置坏, 不是通道挂. 通道挂看 failureReason
5. 加白过期是推断, 后台无显式字段
6. send-logs 翻页 pageSize max 500, 30000+ 只取最近 500 够
7. 包料通道 ROI 高但是别人的料, Willy 不能复制
8. 全网通 GG家 1 条, FTD 率高但成本高

## 红线

- 不自带脚本
- 不落库
- 不自动禁用通道 (SUPER_ADMIN 权限)
- 不联系上游 (加白要 Willy 手工)
- 不猜 balance
- 不跨 backend

## 依赖 skills

```
bowjwj-aicrm             API 地图
bowjwj-conversion-funnel 共用 intelligence
bowjwj-frozen-manager    消费告警
bowjwj-batch-send        consult 黑名单
```
