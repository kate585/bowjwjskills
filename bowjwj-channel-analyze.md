---
name: bowjwj-channel-analyze
description: bowjwj 通道分析。Willy 说"看通道"、"通道排行"、"通道健康"、"通道余额"、"哪个通道好"、"XX 通道咋样"、"通道失败率"、"速度测试"时加载。Globe/Dito 和 Smart/TNT 各自独立通道池，17 条可用通道，三刀合璧分析。
---

# bowjwj-channel-analyze (通道分析)

## 核心原则

- **Globe/Dito 和 Smart/TNT 各有独立通道池**，不混用
- **全网通 (GG家) 两种运营商都能发**，是首选通道
- 排除「包料通道」(对方给料) 和「猫王通道」(需加白)

## 何时触发

**单通道**:
- "看 九 LuckyPlay 通道" / "通道 165b9ca3 咋样"
- "3yo家 余额多少" / "GG家全网通健康吗"

**排行**:
- "通道排行" / "Top 10 通道"
- "哪个通道 ROI 最高" / "哪个通道 CTR 最高"
- "Globe 通道排行" / "Smart 通道排行"

**巡检**:
- "通道健康巡检" / "有通道挂了吗"
- "谁配置坏了" / "谁余额低了"
- "加白过期了吗"

**速度**:
- "速度排名" / "哪个通道最快"
- "测速"

## 通道池

### Smart/TNT 通道 (8 条 — 7 Smart + GG家全网通)

| 简称 | 名称 | 单价 | 备注 |
|------|------|------|------|
| 三 | VKRealm — smart&TNT | 0.004 | |
| 六 | VKQuest — smart&TNT | 0.004 | 4月23新sid |
| 二 | VKVikingWin — smart&TNT | 0.004 | |
| 十 | VKEmpireWin — smart&TNT | 0.004 | 4月23新sid |
| 九 | LuckyPlay S — smart&TNT | 0.004 | 4月23新sid |
| 八 | VKTechVibe — smart&TNT | 0.004 | 4月23新sid |
| 七 | VKVictoryX — smart&TNT | 0.004 | 4月23新sid |
| GG家 | 菲律宾GG家全网通 | 0.004 | ★ 双运营商通用 |

### Globe/Dito 通道 (9 条 — 8 Globe + GG家全网通)

| 简称 | 名称 | 单价 | 备注 |
|------|------|------|------|
| 十五 | LUCKYplay S — Globe&Dito | 0.004 | 4月19新Sid |
| 十四 | LUCKYPLAY S — Globe&Dito | 0.004 | 4月19新Sid |
| 十三 | luckyplay s — Globe&Dito | 0.004 | 4月19新Sid |
| 十二 | luckyplay S — Globe&Dito | 0.004 | 4月19新Sid |
| 十一 | LUCKYPLAY s — Globe&Dito | 0.004 | 4月19新Sid |
| 五 | Luckyplay s — Globe&Dito | 0.004 | 4月19新Sid |
| 四 | Luckyplay S — Globe&Dito | 0.004 | 4月19日新sid |
| 一 | LuckyPlay S — Globe&Dito | 0.004 | |
| GG家 | 菲律宾GG家全网通 | 0.004 | ★ 双运营商通用 |

### 排除规则

```python
def is_usable(ch):
    if not (ch.enabled and ch.type == "sms"): return False
    name = ch.name
    # 包料通道 (对方给料子，不是我们的)
    if any(kw in name for kw in ["包料", "对方给料", "大官人Globe通道"]):
        return False
    # 猫王通道 (需加白才能发)
    if "猫王" in name: return False
    # 必须在 NN33 ph 后端
    if BID not in (ch.backendInstanceIds or []): return False
    return True
```

### 运营商-通道匹配 (8 通道并发)

```python
def ch_carrier(name):
    n = name.lower()
    if "smart" in n and "tnt" in n: return "Smart"
    if "globe" in n and "dito" in n: return "Globe"
    if "GG家" in name or "全网通" in name: return "全网通"
    return None

# 8 通道并发发送:
#   Smart 话术: 7 Smart 通道 + GG家 = 8 通道同时发
#   Globe 话术: 8 Globe 通道 + GG家 = 9 选 8 同时发
#   ★ GG家是双运营商的公共通道，天然可以做跨运营商 CTR 基准对比
```

## 三刀数据源

### 刀 1: `/api/adapters/instances` — 配置 + 余额

```
每条字段:
  id, name, type, enabled
  configJson: driver, host, port, sourceAddr, unitPrice, currency, maxSmsPerSecond
  configInvalidSince — 非 null = 配置坏了
  balance — 余额 (部分通道有)
  backendInstanceIds — 绑定的站点

NN33 ph: enabled=true, type=sms, BID in backendInstanceIds
```

### 刀 2: `/api/intelligence/dimensions?period=7d` — 业绩

```
dimensions.smsChannel:
  funnel: target, delivered, deliveryRate, clicked, ctr,
          registered, registrationRate, ftd, ftdRate
  cost: smsCost, costPerDelivered, costPerClick,
        costPerRegistration, costPerFtd, roi
  compositeScore, rank, tags, trend
```

### 刀 3: `/api/send-logs` — 投递真相

```
GET /api/send-logs?campaignId=<cid>
→ targetCount, successCount, failedCount, dedupSkippedCount
→ failureReason, adapterInstanceId
→ 只看 successCount 算实发，不是 targetCount
```

## 健康判定

```
🔴 挂: configInvalidSince 非空 / enabled=false / 连续 3 次 send-log failed
🟡 警告: balance < 1000 条 / 失败率 >10% / CTR < 全系统中位数 50%
🟢 健康: 以上都不满足
```

## 通道排行输出格式

```
🏆 Globe/Dito 通道排行 (按 ROI)
1. GG家全网通 | ROI=3.53 | CTR=4.5% | FTD=1 | 余额=XXXXX
2. LuckyPlay一 | ROI=X | CTR=X% | ...
...

🏆 Smart/TNT 通道排行 (按 ROI)
1. VKRealm(三) | ROI=X | CTR=X% | ...
...
```

## 速度测试

```bash
# 历史测速结果
cat "/c/Users/jack8/Desktop/bowjwj 发送模式更新脚本文件夹2/speed_ranking_results.json"
```

## 成本

- 0.21 PHP / 条 (Smart&TNT / Globe&Dito)
- GG家全网通: 0.004 (单价不同，需确认单位)
- dedup 率 15-25% (号码包质量越好越低)

## 禁区

- ❌ 不在禁用的通道上创建 campaign
- ❌ 不对 configInvalidSince 非空的通道发信
- ❌ Globe 包不发 Smart 通道，Smart 包不发 Globe 通道 (全网通除外)
- ✅ 自由: adapters/instances GET、intelligence/dimensions GET

## 多通道并发对比 (8 通道同时发 = 天然 A/B)

GG家全网通是双运营商公共通道，8 通道同时发时自动产生对比数据：

```
同一条话术，同一包号码，同时发 8 个通道:
  三 VKRealm        → 看 CTR
  六 VKQuest        → 看 CTR
  二 VKVikingWin    → 看 CTR
  十 VKEmpireWin    → 看 CTR
  九 LuckyPlay S    → 看 CTR
  八 VKTechVibe     → 看 CTR
  七 VKVictoryX     → 看 CTR
  GG家全网通        → 基准 CTR (跨运营商对比锚点)

对比维度:
  1. 单通道 CTR vs 其他 7 通道 → 通道质量排名
  2. 所有通道 vs GG家全网通 → 全网通是不是真的最优
  3. 同通道不同话术 CTR → 话术质量排名 (跨轮对比)
  4. 新 sid (4月23) vs 旧 sid → sid 刷新效果
```

### 通道变更记录

```
2026-04-28: Globe侧新增十二( luckyplay S )，移除十六
            现 Globe=8+1, Smart=7+1, 合计 17 通道
            GG家全网通 = 双运营商基准通道
```
