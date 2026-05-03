---
name: bowjwj-best-daily-copy
description: bowjwj 最佳日文案流水线。Willy 说"最佳日文案"、"今日最佳文案"、"日文案优选"、"跑日文案"、"7天最佳文案"时加载。四步闭环：7天数据抓取Top50→AI衍生50条→100条测试→精选30条今日发送。
---

# bowjwj-best-daily-copy (最佳日文案)

## 核心流水线

```
Step 1: 抓取近7天Top50文案 (高CTR + 大发送量 + 有FTD)
Step 2: AI衍生50条 (保留赢家模式，变异措辞)
Step 3: 100条并发测试 (每条2000条，8通道)
Step 4: T+60min 精选Top30 → 入库今日发送池
```

## 🔴 铁律

### 1. Globe/Smart 分开排名，各出25条Top + 25条衍生 = 各50条测试
### 2. 必须确保有首充(FTD>0)才入选，纯CTR高但无充值=废文案
### 3. 衍生文案必须过5条硬规则 + 红线检查
### 4. 测试用8通道并发，降低代理线占用
### 5. 最终30条：Globe 15 + Smart 15 = 今日发送文案池

## 何时触发

**启动**:
- "最佳日文案" / "今日最佳文案" / "日文案优选"
- "跑日文案" / "7天最佳文案" / "更新今日发送文案"

**查看**:
- "日文案进度" / "Top50有哪些"
- "衍生文案好了吗" / "测试结果"

## Step 1: 抓取近7天Top50文案

### 数据源

```
1. 主数据源: send-logs (发送量) + operations-report (FTD/注册)
2. 辅助: campaign-templates (拿smsText)
3. 时间范围: startDate=7天前, endDate=今天
4. 后端: c7ee7c4c-ce0a-49c9-880a-9315d07c07b6 (NN33 ph)
```

### 查询流程

```python
# 1. 查最近campaigns (有templateId关联的)
campaigns = GET /api/campaigns?backendInstanceId=<BID>&limit=500&sort=createdAt&order=desc

# 2. 对每个campaign查 send-logs (拿发送量+success/fail)
for cid in campaign_ids:
    logs = GET /api/send-logs?campaignId=<cid>

# 3. 查 operations-report 拿 FTD/deposit
report = GET /api/operations-report?backendInstanceId=<BID>&groupBy=campaign&startDate=<7d>&endDate=<today>

# 4. 查 campaign-templates 拿文案内容
templates = GET /api/campaign-templates?backendInstanceId=<BID>&limit=500
```

### 评分公式

```
综合分 = CTR% × 0.3 + FTD_count × 0.4 + deposit_amount_norm × 0.2 + sent_volume_norm × 0.1

条件:
  - CTR >= 3% (最低门槛)
  - FTD > 0 (必须有首充)
  - sentCount >= 500 (最低发送量)
  - 过滤: smsText不含黑名单词
```

### 输出格式

```
top50_copies.json:
[
  {
    "rank": 1,
    "templateId": "xxx",
    "templateName": "xxx",
    "carrier": "globe|smart",
    "smsText": "...",
    "ctr": 6.5,
    "ftdCount": 12,
    "depositAmount": 5800,
    "sentCount": 15000,
    "score": 87.5
  },
  ...
]
```

## Step 2: AI衍生50条

### 衍生规则

```
输入: Top25 Globe + Top25 Smart (各语言独立衍生)
输出: Globe 25条新 + Smart 25条新 = 50条衍生

衍生策略 (每条原文案 → 1条衍生):
  1. 保留核心金额锚点 (P5,288 / P3,888等) — 这是转化关键
  2. 保留紧迫感结构但不重复原话术
  3. 变换Taglish病词组合 (na/mo/lang/pa 交替)
  4. 变换句式: 陈述句→疑问句、主动→被动
  5. 变换时间压力: midnight→bukas→ngayon→hanggang
  6. 保持 130-145 字符长度
  7. 过5条硬规则 + 红线检查
```

### 5条硬规则

1. 开头不放品牌名大写
2. 不能全英文 — 植入1-2个Taglish病词
3. 不超过1个感叹号
4. 不用祈使句 (Claim now → pwede mo na makuha)
5. 不超过145字符

### 红线一票否决

博彩促销词: ACT NOW / CLAIM NOW / DEPOSIT NOW / URGENT / FREE SPIN / LIMITED TIME / LAST CHANCE
赌博黑名单: BET / BONUS / DEPOSIT / CASINO / FREE / CLAIM / REWARD / PROMO / SPIN / JACKPOT / RAFFLE / PRIZE
品牌名: OKBET / PBAHAY / NN33

### 衍生后验证

每条衍生文案必须:
- ✅ 与原文不同 (Levenshtein距离 >= 20)
- ✅ 含2-3个Taglish病词
- ✅ 不碰红线
- ✅ 字符数 <= 145

## Step 3: 100条并发测试

### 测试配置

```
每条文案: 8通道 × 1包 = 800条同时发出
每条完成: 3轮 (800+800+400 = 2000条)
通道分配: Globe文案→Globe通道池, Smart文案→Smart通道池
票卷: FREE_SPIN 2804039 (统一)
模板: AI发送-valuehook-v2-01 (604ed445)
短链模式: domain
```

### 测试节奏

```
100条 × 2000条 = 20万条测试量
每3秒: 1文案 × 8通道 × 1包 (800条)
每秒 = 266条, 全天产能足够

Globe线: 50条 × 2000 = 10万条
Smart线: 50条 × 2000 = 10万条
```

### 测试API调用

```
POST /api/campaigns
{
  templateId: <衍生文案模板ID>,
  ticketRewards: [{ticketType:"FREE_SPIN", ticketId:"2804039", ticketQuantity:1}],
  smsInstanceIds: [8个通道],
  phonePackIds: [1个包],
  ...
}
```

### 测试监控

```
T+30min: 查replay-dashboard/batches/<batchId> 拿PH IP CTR
T+60min: 查operations-report 拿FTD
持续: 监控每个campaign的CTR和FTD
```

## Step 4: 精选Top30

### 精选标准

```
CTR >= 5% 且 FTD > 0 → 直接入选 (优先级最高)
CTR >= 3% 且 FTD > 0, 按 (CTR×0.5 + FTD×0.5) 排序补足
CTR < 3% 或 FTD=0 → 淘汰

最终: Globe 15条 + Smart 15条 = 30条今日发送文案
```

### 输出

```
今日发送文案池 (30条):
  Globe (15):
    1. [tpl_id] smsText... | CTR=7.2% FTD=8 | 综合=92
    2. ...
  Smart (15):
    1. [tpl_id] smsText... | CTR=6.8% FTD=6 | 综合=88
    2. ...

入库: 更新 auto_send.py GLOBE_TPL / SMART_TPL (如果当日只用这30条)
      或: 写入 best_daily_copies.json 供 auto_send.py 读取
```

## 每日时间线 (BJ)

```
00:00-07:00  休息
07:00        自动抓取7天数据 → Top50
07:00-07:30  AI衍生50条 + 验证
07:30        POST创建100条测试campaign
07:30-14:00  6.5h测试窗口 (3秒间隔足够测完20万条)
14:00-15:00  汇总CTR+FTD → 精选Top30
15:00        输出今日发送文案池
15:00-23:00  用Top30进行正式发送
```

## 执行脚本

脚本位于: `/Users/kate/.claude/skills/bowjwj-best-daily-copy/run_pipeline.py`

### 用法

```bash
# 完整流水线
python3 run_pipeline.py --full

# 单独步骤
python3 run_pipeline.py --step1-only    # 只抓取Top50
python3 run_pipeline.py --step2-only    # 只衍生
python3 run_pipeline.py --step3-only    # 只测试
python3 run_pipeline.py --step4-only    # 只精选

# 指定日期范围
python3 run_pipeline.py --days 7 --end-date 2026-05-03
```

### 输出文件

```
~/.hermes/state/bowjwj/
  daily_copy_pool_100.json  # Step1+2合并: 100条文案池 (50原始+50衍生)
  top_copies_7d.json -> /tmp/top_copies_7d.json  # Step1中间产物

/tmp/
  top_copies_7d.json        # Step1 抓取结果 (replay-dashboard)
  derived_50_copies.json    # Step2 衍生结果
```

### 2026-05-03 实际数据

**Step 1**: 从replay-dashboard拉1000条batch(FTD desc前10页) + campaigns API关联finalSmsContent
- 317条unique batch有FTD/deposit, 全部匹配到SMS文案
- Top1: `may P5,288 na pumasok sa account mo, check mo na bago mag-midnight ${shortUrl}` — FTD=57, dep=81380, sent=110072, CTR=7.0%, 103批次

**Step 2**: AI衍生50条 — 保留Taglish悬念模式，变换金额/句式/病词组合

**Step 3-4**: 待执行 — 100条测试+精选30条

### 实战教训

1. **intelligence/dimensions API不可用** — 返回INTERNAL_ERROR，必须用replay-dashboard/batches
2. **operations-report API也不可用** — 同样INTERNAL_ERROR
3. **唯一可用数据源**: replay-dashboard/batches (有ftdCount/depositAmount/CTR/sentCount)
4. **campaigns API** 返回 `finalSmsContent` 字段 = 实际发送文案，用于关联batch和文案
5. **关联方式**: campaign.campaignBatchId = replay-dashboard.batch.batchId
6. **批量关联效率**: 先拉全部batches(FTD>0)，再拉全部campaigns(7天)，内存join，比逐个batch查campaign快100x
