---
name: bowjwj-copy-analyze
description: bowjwj 话术分析。Willy 说"文案排名"、"看 CTR"、"哪个话术好"、"文案对比"、"模板衰减"、"A/B 文案"、"学学高转化文案"、"话术排行榜"时加载。Globe/Dito 和 Smart/TNT 分开排名，CTR 只看菲律宾 IP。
---

# bowjwj-copy-analyze (话术分析)

## 核心原则

- **Globe 和 Smart 分开排名**，不混排 (用户群行为不同)
- **CTR 只看菲律宾 IP** (美国 UV 污染严重，130 条量级 3 个假 UV = 2% 虚高)

## 何时触发

**排名**:
- "文案排名" / "话术排名" / "top 50"
- "最近 3 天哪个文案好" / "Globe 话术排行" / "Smart 话术排行"
- "文案 CTR 排名"

**单模板分析**:
- "看 G1 话术效果" / "S3 CTR 多少"
- "模板 16586cb8 数据分析"

**对比**:
- "A/B 文案对比: G1 vs G2"
- "同通道不同模板对比"
- "Globe 6 方向哪个最好"

**衰减**:
- "模板衰减" / "G1 是不是衰减了"
- "话术疲劳检测"

**学习**:
- "学学高转化文案" / "高 CTR 文案特征"
- "全系统标杆文案"

## 数据口径

### ⚠️ CTR 必须只看菲律宾 IP

```
错误: 直接用 shortlink visits 全部点击算 CTR
  → 美国 Google/bot prefetch 污染
  → 130 条量级下 3 个假 UV = 2% 虚高

正确: 过滤 isBot=false AND country=PH (或 IP 在 PH 段)
  → 真实菲律宾用户点击
  → 数据源: replay-dashboard.batches[].trafficDetails.regionBreakdown
```

### 数据源

**主**: `/api/intelligence/dimensions?period=3d&backendInstanceId=<BID>`
```
dimensions.textCopy (500 条):
  dimensionKey / dimensionLabel / campaignCount
  funnel: target, delivered, deliveryRate, clicked, ctr, 
          registered, registrationRate, ftd, ftdRate
  cost: smsCost, costPerDelivered, costPerClick, 
        costPerRegistration, costPerFtd, roi
  scores: deliveryScore, clickScore, registrationScore, 
          ftdScore, roiScore, costEfficiencyScore
  compositeScore, rank, trend (stable/rising/falling)
  tags: [{code, label, sentiment}] (best_overall/high_convert/high_roi)
  radar: {axes: [6轴], ...}
```

**辅**: `operations-report?groupBy=campaign` — 自己的模板表现

**本地**: `stats.db.batches` — 历史 CTR (PH IP 过滤后)

## Globe/Dito 话术排名 (输出格式)

```
🥇 G1-到账+限时 | CTR=11.81% | 28/237 | 综合96.36 | rising ↑
🥈 G2-到账+明天到期 | CTR=X% | ...
...
```

## Smart/TNT 话术排名 (输出格式)

```
🥇 S6-对话式 | CTR=X% | ...
...
```

## 衰减检测

```
判定: 最近 7 天 CTR 比前 7 天下降 >30%
处理: 
  - 标记 decay 告警
  - 自动从轮换池降权
  - 建议换同方向新话术
  - 如连续 14 天衰减 → 建议冻结

数据源: stats.db.batches, 按 (template_id, carrier) GROUP BY week
```

## A/B 对比规则

```
对比条件: 同运营商 + 同通道 + 同时间段
公平对比: sent >= 500 (量级不够不对比)
显著性: CTR 差 >2 个百分点才算真差异

输出: 
  - CTR 差异 + 显著性判定
  - 注册率差异
  - FTD 率差异
  - 综合建议 (换/不换)
```

## 跨运营商学习

```
规则: Globe 验证过的方向 → 可生成 Smart 对等版测试
限制: 不等于照抄，需调整病词和金额数字
案例: G1 (到账+限时, CTR 11.81%) → 生成 S1 对等版

禁止: Smart 验证过的方向直接搬 Globe (用户群差异大)
推荐: 从 Globe 学习 → 在 Smart 独立测试 → Smart 独立验证
```

## 高点击文案模式库

### 已验证最高 CTR 模式

| 模式 | CTR | 示例 |
|------|-----|------|
| 到账金额+限时领取 | 11.81% | `may P5,888 na naka-load sa account mo, valid hanggang Apr 30` |
| Taglish 对话式 | 4.5% | `may update lang sa account mo, check na lang pag may time ka` |
| 金额悬念 | TBD | `meron kang P2,988 na na-add sa wallet` |
| 朋友语气 | TBD | `uy check mo nga account mo, may P3,888 na naka-pending` |

### 已知低 CTR 模式 (避免)

| 模式 | CTR | 原因 |
|------|-----|------|
| 奖金/红包类 | 0% | Google 垃圾模型直接过滤 |
| Urgent/Act Now | 0% | 垃圾短信经典特征 |
| 纯英文促销 | <0.5% | 无菲律宾病词 = 无防护 |

## 本地命令

```bash
# 文案排行榜 (最近 3 天)
python3 ~/.hermes/state/bowjwj/ranking.py

# 查看文案库
cat "/c/Users/jack8/Desktop/bowjwj 发送模式更新脚本文件夹2/高点击文案库.txt"
```

## 禁区

- ❌ 不用全量 visits 算 CTR (含 bot)
- ❌ Globe 和 Smart 不混排
- ❌ 不接受 <100 sent 的 "CTR" 数字 (量级太小无统计意义)
- ✅ 自由: 所有 GET 分析 API
