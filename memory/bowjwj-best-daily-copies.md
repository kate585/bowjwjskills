---
name: bowjwj-best-daily-copies
description: Iron rule — daily pull top 50 copies (CTR+volume+FTD) from last 7 days, derive 50 more, test 100, pick best 30
type: feedback
originSessionId: current
---
## 铁律: 每日文案选优流水线 (2026-05-03)

**每天执行一次：从近7天数据中抓取CTR最高+发送量大+有首充的50条文案 → AI衍生50条 → 100条发送测试 → 取30条最佳作为当日发送文案。**

### Step 1: 抓取近7天 Top 50
- 数据源: `GET /api/replay-dashboard/batches` (pageSize=100, 拉取所有页)
- 聚合: 按 campaignName 去重(sum sent, clicks, rawClicks, FTD, deposit, regs)
- 排序: FTD>0 优先, 然后 clicks×sent 复合分
- 过滤: CTR>=3%, sent>=500
- 取 Top 50

### Step 2: 查模板 SMS 文案
- 对 Top 50 的 campaign → GET /api/campaigns/{id} → templateId
- GET /api/campaign-templates/{templateId} → smsText
- 输出: 50条原始文案文本

### Step 3: AI 衍生 50 条
- 基于 Top 50 的 Taglish 风格、句式、金额模式
- 保持 Taglish 口语化、对话感
- 每条结尾带 `${shortUrl}`
- 不重复原50条的核心句式

### Step 4: 100 条发送测试
- 创建 100 个模板 (batch POST /api/campaign-templates)
- Smart + Globe 各建 100 个(=200个模板, 100条文案×2运营商)
- 每个模板发 1 轮 test-send (1包, skipPolling)
- T+120s 查 CTR

### Step 5: 取 30 条最佳
- 排序: CTR desc, FTD desc
- Top 30 → 更新 send_rules.json copyPoolTemplateIds
- 其余 70 条标记备用

**Why:** Willy 要求基于真实数据驱动文案选择，每天自动优化文案池，用近7天验证过的爆款文案+AI衍生扩大覆盖面，再经过实发测试筛选，确保当日发送的都是最优文案。

**How to apply:**
- 每天发信前执行一次完整流水线
- 如果当日已有有效结果(同一天内)，跳过 Step 1-3，直接用缓存的 Top 30
- 输出结果存 ~/.hermes/state/bowjwj/best_daily_copies/{YYYYMMDD}/
