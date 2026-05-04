# bowjwj 最佳日文案 skill

## 触发条件
Willy 说 "最佳日文案" / "今日最佳文案" / "best daily copy" / "日文案优化" / "挑选最佳文案"

## 流程总览

```
Step 1: 抓取最近7天 operations-report 数据
Step 2: 按 CTR×发送量×FTD 综合评分排名 → 取 Top 50
Step 3: AI 衍生 50 条新文案（基于 Top 50 的 Taglish 模式）
Step 4: 创建 100 条模板到 bowjwj (50 原始 + 50 衍生)
Step 5: 测试发送 (每模板 2000 条)
Step 6: T+60min 查 CTR → 取 Top 30 入库为今日发送文案
Step 7: 更新 auto_send.py COPY_POOL
```

## Step 1: 数据抓取

```bash
JWT=$(cat ~/.hermes/state/bowjwj/.jwt)
# 分两批避免超时
curl -s --max-time 30 "$BASE/api/operations-report?dateFrom=<7天前>&dateTo=<昨天>&backendInstanceId=$BID&groupBy=campaign" \
  -H "Authorization: Bearer $JWT" -o /tmp/ops_report.json
```

## Step 2: 排名算法

```python
score = CTR(%) × ln(sent + 1) × FTD
# 过滤: FTD > 0, sent >= 1000
# 排除: 全英文 (无 Tagalog 粒子), 含红线词
```

红线词清单: ACT NOW / CLAIM NOW / FREE SPIN / FREE BONUS / LIMITED TIME / LAST CHANCE / HURRY UP / DON'T MISS / BET / CASINO / JACKPOT / RAFFLE / PRIZE

## Step 3: AI衍生规则

- 保留原作文案结构 (英文骨架 + 1-2个菲律宾词)
- 替换金额数字 (P2,588 / P3,588 / P4,188 / P5,288 / P5,888 / P6,288 / P7,288)
- 替换Tagalog粒子 (na / mo / lang / pa / ba / ka / nga / pala / dyan / oh)
- 替换动词短语 (pumasok→dumating / na-credit→na-add / check→tingnan / claim→kunin)
- 保持 ≤145 字符
- 禁止非ASCII字符
- 开头小写 (不放品牌名大写)
- 不超1个感叹号

## Step 4: 模板创建

```bash
POST /api/campaign-templates
body: {
  name: "0503best-{序号}",
  activityName: "0503ai-best-test",
  backendInstanceId: "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6",
  campaignType: "activity",
  smsText: "<文案> ${shortUrl}",
  ticketRewards: [{"ticketType":"RAFFLE","ticketId":"2804039","ticketQuantity":1}],
  status: "active"
}
```

## Step 5-6: 测试 & 筛选

- 每模板配 1 通道 (Globe/Smart 各半)
- 发送量: 每模板 2000 条
- T+60min 查 CTR
- 按 CTR 排名取 Top 30

## Step 7: 更新发送配置

更新 auto_send.py:
- 替换 COPY_POOL 为 Top 30
- 更新 TEMPLATE_ID 为最佳模板
- 记录更新日志
