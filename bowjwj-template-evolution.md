---
name: bowjwj-template-evolution
description: bowjwj 模板迭代协调器。Willy 说"看模板"、"模板排行"、"模板衰减"、"A/B 模板"、"学学高转化文案"、"AI 生成模板"、"AI 改写 #T"、"模板健康"时加载。intelligence/dimensions textCopy 看全系统 Top, operations-report 看自己的模板表现, campaign-templates/ai-generate + ai-regenerate-sms 走 AI 改写。只协调, 不自带脚本。
---

# bowjwj-template-evolution (协调器)

## 何时触发

**查询**:
- "看模板" / "我的模板效果"
- "模板排行" / "Top 10 模板"
- "看 大官人加白2 模板"
- "模板衰减" / "衰减识别"

**对比**:
- "A/B 模板: 大官人加白 1 vs 2 vs 3"
- "同通道不同模板对比"

**学习 / 创作**:
- "学学全系统高转化文案"
- "高 CTR 模板特征"
- "AI 生成新模板"
- "AI 改写 #T (某模板 id)"

**巡检**:
- "模板健康巡检" (扫 33 个 active NN33 ph, 识别该冻的)

## 协调目标

薄协调层, 3 个 API 组合:
1. **intelligence/dimensions textCopy** 市场 Top / 基线
2. **operations-report** Willy 自己模板表现
3. **ai-generate / ai-regenerate-sms** 创作新模板

不落库, 实时. 判定逻辑硬编码.

## 三刀数据源

### 刀 1: intelligence/dimensions (市场 / 学习)

```
GET /api/intelligence/dimensions?period=7d&backendInstanceId=<BID>
  → dimensions.textCopy (500 条)
  
每条字段:
  dimensionKey          templateId 或 textId
  dimensionLabel        模板名 / SMS 预览前 N 字
  campaignCount         用过几次
  funnel                target/delivered/ctr/ftdRate ...
  cost / scores / radar / tags / trend

★ 全系统, 不是个人. 看 Top 1-10 学标杆
```

### 刀 2: operations-report (自己的)

```
GET /api/operations-report?
    backendInstanceId=<BID>
    createdByUserId=<我>
    groupBy=campaign
    dateFrom / dateTo

每行 batchSmsText + funnel + cost
按 SMS 文本特征人工 / AI group 分析
```

### 刀 3: campaign-templates AI (创作)

```
★ AI 生成新模板:
POST /api/campaign-templates/ai-generate
body: {
  backendInstanceId,
  campaignType,
  phonePackIds,        必须真包, 用来参考目标号码
  goal,                   "high_click" / "high_ftd" / "reactivation"
  tone,                   "casual" / "urgent" / "reward"
  variants: 3-5           生成几版
  ...
}
返回: suggestions[] { smsText, rationale, requiredVariables }

★ AI 重写现有模板:
POST /api/campaign-templates/ai-regenerate-sms
body: { templateId, backendInstanceId, style, requiredVariables, ... }
返回: { smsText, rationale }

★ 权限: TEXT_MANAGE (OPS_ADMIN 有)
```

## 视图组装

### 1) 我的模板效果 "看模板"

```
GET operations-report groupBy=campaign dateFrom=-30d
聚合 batchSmsText (本地按相似度 group)
OR 直接 GET campaign-templates 拿 tpl_id 列表
对每 tpl_id 反查 campaigns + send-logs 算漏斗

简化: 直接从我创建过的 campaigns 按 templateId 聚合

输出:
  模板名 · 用过几次 · 近 30d sent · click · reg · ftd · ROI · trend
```

### 2) 市场 Top "学学高转化文案"

```
GET intelligence/dimensions textCopy Top 20 by compositeScore
过滤:
  campaignCount >= 5      样本足
  ftdRate > 5%            真正转化
  roi > 1                 真盈利

输出每条:
  文案前 60 字 / CTR / 注册率 / FTD 率 / ROI
  tags: [high_convert, high_roi...]
  
💡 AI 抽特征 (不是自动, 是 Willy 问时说):
  "这 10 个 Top 文案的共性是什么?"
  AI 对话分析: 长度 / 关键词 / 语气 / 奖励表达 / URL 位置
```

### 3) A/B 对比 "大官人加白 1 vs 2 vs 3"

```
查 3 个 templateId
对每个: operations-report groupBy=campaign, sumBy templateId
表格:
  模板名 · campaigns · sent · CTR · 注册率 · FTD 率 · ROI · 置信度
  
置信度: 样本 < 500 标 "样本小不可靠"
```

### 4) 衰减识别 "模板衰减"

```
对每 active 模板按周查:
  week1 CTR vs week4 CTR
  降幅 > 30% → 衰减中
  降幅 > 50% → 建议下架

输出:
  衰减模板清单 (seq 影响 + 降幅 + 建议)
```

### 5) AI 生成 "AI 生成 3 版模板 high_click"

```
POST /api/campaign-templates/ai-generate
{
  backendInstanceId: BID,
  campaignType: "activity",
  phonePackIds: [最近某包],        必需
  goal: "high_click",
  tone: "casual",
  variants: 3,
}

AI 返回 suggestions[0..2]:
  smsText / rationale
  
Willy 看 -> 选哪版 -> 后续可手动创建 template (本 skill 不自动建)
```

### 6) AI 重写 "AI 改写 #T (5e9b5281 加白3)"

```
POST /api/campaign-templates/ai-regenerate-sms
{
  templateId: "5e9b5281-...",
  backendInstanceId: BID,
  style: "更紧迫" / "更奖励感" / "换表达",
  requiredVariables: ["phone", "shortUrl"]
}

返回新 smsText + rationale
Willy 看 → 决定是否覆盖原模板 (本 skill 不自动覆盖)
```

## 判定阈值

| 指标 | 阈值 | 动作 |
|------|------|------|
| 衰减 > 50% | 跨 4 周 | 红 建议下架 |
| 衰减 30-50% | 跨 4 周 | 黄 观察 |
| ftdRate < 0.5% | campaigns >= 10 | 红 低转化 |
| ftdRate > 10% | campaigns >= 5 | 绿 标杆 |
| ROI < 0.3 | campaigns >= 10 | 红 亏本 |
| ROI > 3 | campaigns >= 5 | 绿 高回报 |

## 与其他 skill 边界

```
bowjwj-frozen-manager:
  本 skill 产 "模板级红告警" → 建议 frozen_template
  不自动冻, 输出给 frozen-manager

bowjwj-batch-send:
  发起前 consult 本 skill 黑名单 (衰减模板)

bowjwj-conversion-funnel:
  共用 intelligence / operations-report, 别重拉

bowjwj-channel-health:
  兄弟 skill, 通道视角; 本 skill 模板视角; 数据互补
```

## 已知坑

1. intelligence textCopy Top 可能是"小陈 100 包 43"单次高光, 必须 campaignCount >= 5 才参考
2. campaigns.templateId 是真模板 id, batchSmsText 是实际发出文本, 可能差异 (插 phone/shortUrl)
3. 模板 id 和 textId 不是一回事: textId 是变体, templateId 是母版
4. ai-generate 要求 phonePackIds, 它会基于号码特征调 AI prompt
5. ai-regenerate-sms 只改文本, 不改奖励 ticketRewards / activityName
6. AI 返回 rationale 要让 Willy 看到, 不只给 smsText
7. 生成后不自动创建模板, 要 Willy 手动 POST /api/campaign-templates 落地
8. requiredVariables 必须带, 不然返回的模板缺占位符

## 红线

- 不自带脚本
- 不自动覆盖模板
- 不自动禁用
- 不跨 backend
- 不 AI 生成后直接发 (要 Willy 过审)
- AI 生成必须带 rationale 给 Willy

## 依赖 skills

```
bowjwj-aicrm             API 地图 (模板 CRUD)
bowjwj-conversion-funnel 共用 operations-report
bowjwj-channel-health    互补兄弟
bowjwj-frozen-manager    消费告警
bowjwj-batch-send        发起前 consult
```
