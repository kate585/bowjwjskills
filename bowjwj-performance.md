---
name: bowjwj-performance
description: bowjwj 效果分析。Willy 说"看效果"、"#68 效果"、"今天发了多少"、"ROI"、"FTD"、"注册多少"、"转化漏斗"、"batch 效果"、"看库存"、"包健康"、"供应商 ROI"时加载。业务口径为主 (replay-dashboard)，技术口径为辅 (send-logs/visits)。
---

# bowjwj-performance (效果分析)

## 核心原则

- **业务口径 > 技术口径**: replay-dashboard / operations-report 是主源，send-logs / visits 只用于排障
- **CTR 只看菲律宾 IP** (防美国 UV 污染)
- **FTD 是唯一真金白银**，reg >= 2 才算有效 (防 agent_line 自带伪信号)

## 何时触发

**单 batch/seq 钻取**:
- "#68 效果" / "看 BATCH-xxx" / "seq68 CTR"
- "campaign d130c027 效果"

**时段汇总**:
- "今天效果" / "最近 24h" / "最近 7 天"
- "今天发了多少" / "今天点击多少"
- "今早发了啥"

**转化漏斗**:
- "转化漏斗" / "看 FTD" / "ROI 多少"
- "今天赚了多少" / "注册效果"

**库存**:
- "看库存" / "包健康" / "号码还剩多少"
- "Smart 包够用吗" / "采购预警"

**供应商**:
- "供应商 ROI 排行" / "料子质量"
- "XX 来源的料效果"

## 数据口径

### 业务口径 (主源)

```
GET /api/replay-dashboard/batches/<batchId>
  → headline.traffic: rawClicks, clicks, uv, pv, ipCount, ctr
  → headline.conversion: registrations, ftdCount, depositAmount, 
                          validBettingAmount, netPnlAmount
  → headline.cost: smsCost, costPerClickUv, costPerRegistration
  → funnel: target → delivered → clicked → registered → ftd
  → quality: pvUvRatio, ipUvRatio, newVisitorRate
  → ai: promptSummary, metrics.roi, topPacks, bottomPacks
  → packs[]: per-pack score/summary
  → lines[]: per-agent-line reg/ftd/deposit

GET /api/operations-report?backendInstanceId=<BID>&createdByUserId=<me>&groupBy=campaign
  → sentCount, clicks, uv, registrations, ftdCount
  → depositAmount, validBettingAmount, commission
  → smsCost, registrationCost, ftdCost, roi, roas
  → netAmount, netProfit
```

### 技术口径 (排障用)

```
GET /api/send-logs?campaignId=<cid>
  → targetCount, successCount, failedCount, dedupSkippedCount

GET /api/shortlinks/<slid>/visits
  → visitedAt, ip, userAgent, isBot (流水，缺 reg/ftd)
```

### ⚠️ sharedBatch 陷阱

```
错误: 把 packs[0].successCount 当 batch 总 sent
正确: batch sharedBatch=true 时 total_sent = sum(p.successCount for p in packs)
```

## 效果查询输出格式

### 单 batch 详情

```
#68 | seq68-20260424-0646 | Smart | VKRealm(三)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📨 发送: 135 sent / 135 target / 65 dedup (32.5%)
👆 点击: 3 clicks / 3 UV / CTR=2.22% (PH IP)
📝 注册: 3 reg / 1 FTD
💰 收入: 100 PHP deposit / 176.3 valid betting
📊 ROI: 3.53 | AI评分: 96.36
🏷️  质量: pvUvRatio=1 (不作弊) | newVisitorRate=100%
```

### 时段汇总

```
📅 2026-04-28 汇总
━━━━━━━━━━━━━━━━━━━━
📨 发送: 32,042 条
👆 点击: 14 (CTR=0.04%)
📝 注册: X | FTD: X
💰 ROI: X
🔴 零点击组合: X 个
```

## 号码包库存

```
GET /api/phone-packs?pageSize=2 → total
NN33 ph: 42,574 包 (BID=c7ee7c4c-...)

按运营商:
  Smart/TNT: X 包 (X 条)
  Globe/Dito: X 包 (X 条)
  黑名单: 347 包 (跳过)
  全网通: X 包

按来源:
  银河数据0427: X 包 (X 条) ★ 优先
  ...

老化包: >7 天未用 X 包
reuseLocked: X 包
采购预警: <阈值时触发
```

## 供应商 ROI (本地 stats.db)

```
供应商 | 采购量 | 已用量 | 点击 | CTR | 注册 | FTD | ROI
银河   | 5000   | 3000   | 45  | 1.5%| 3   | 1  | 2.1
龙少   | 3000   | 1000   | 5   | 0.5%| 0   | 0  | 0
```

## 本地查询命令

```bash
# 单 batch 详情
python3 ~/.hermes/state/bowjwj/analyze.py batch <batch_id>

# 时段汇总
python3 ~/.hermes/state/bowjwj/analyze.py summary

# 组合 CTR 排名
python3 ~/.hermes/state/bowjwj/analyze.py combos

# 成本分布
python3 ~/.hermes/state/bowjwj/analyze.py cost
```

## 禁区

- ❌ 不用 shortlink visits 汇报业务效果 (漏 reg/ftd)
- ❌ reg=1 不算有效注册 (agent_line 伪信号)
- ❌ 不用 cleanCount 估算 sent_count (用 send-log successCount)
- ✅ 自由: replay-dashboard GET、operations-report GET、phone-packs GET
