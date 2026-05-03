---
name: bowjwj-ranking-daily
description: bowjwj 文案效果排行榜。Willy 说"排行榜"、"文案排名"、"top 50"、"最近3天哪个文案好"、"文案CTR排名"时加载。每天自动更新最近3天文案CTR(PH IP)、注册转化、首充转化、综合评分前50名，输出txt文档。
---

# bowjwj-ranking-daily (文案排行榜协调器)

## 何时触发

**查询**:
- "排行榜" / "文案排名" / "top 50"
- "最近3天哪个文案好"
- "文案CTR排名"
- "看文案效果排名"

**自动** (cron):
- 每天 BJ 08:00 自动跑一次，生成排行榜 txt

## 协调目标

薄协调层。调 `generate_ranking.py` 拉 bowjwj 后台数据，按 4 维度加权评分排出最近 3 天 top 50 文案，输出格式化 txt 到桌面。

## 数据源

### 主: `/api/intelligence/dimensions` (模板级评分)
```
GET /api/intelligence/dimensions?period=3d&backendInstanceId=<NN33_BID>
→ dimensions.textCopy (按 compositeScore 排序)
→ 每条含: funnel(ctr/registrationRate/ftdRate), cost(roi), scores(6维), radar, tags
```

### 辅: `/api/operations-report` (转化归因)
```
GET /api/operations-report?
  backendInstanceId=<BID>
  dateFrom=<3天前> dateTo=<今天>
  groupBy=campaign
→ 每条含: registrations/ftdCount/depositAmount/smsCost/roi
```

### PH IP 过滤: `/api/replay-dashboard/batches/<batchId>`
```
regionBreakdown → 只取 PH 的 clicks/uv
PH_CTR = PH_clicks / success_count
```

## 4 维度加权评分

| 维度 | 权重 | 数据源 | 计算 |
|------|------|--------|------|
| PH CTR | 25% | replay regionBreakdown | PH_clicks / sent |
| 注册转化 | 25% | operations-report | registrations / uv |
| FTD 转化 | 30% | operations-report | ftdCount / registrations |
| AI 综合分 | 20% | intelligence scores | compositeScore 归一化 |

**加权公式**: `final_score = CTR_z × 0.25 + REG_z × 0.25 + FTD_z × 0.30 + AI_z × 0.20`

## 运行方式

```bash
# 手动跑
python3 ~/.claude/skills/bowjwj-ranking-daily/generate_ranking.py

# 输出位置
ls ~/Desktop/bowjwj_ranking_$(date +%Y%m%d).txt

# cron 每天 08:00 BJ 自动跑 (通过 hermes cron 或技能内 cron)
```

## 输出格式 (top 50 txt)

```
🏆 bowjwj 文案效果排行榜 · 2026-04-28 (最近3天)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
更新: 2026-04-28 08:00 BJ | 数据窗口: 04-25 ~ 04-28
PH IP 过滤: ✅ | 样本阈值: ≥100 sent

Rank 模板名                            PH CTR  注册率  FTD率  综合分
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1  NN33 到账领取 P333               3.2%   8.5%  12.0%  94.2
  2  大官人加白模版 2                  2.8%   7.1%  10.5%  89.7
  ...
 50  NN33 汤丁 高转化测试              0.8%   1.2%   0.0%  45.3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 统计摘要:
  上榜模板数: 50 (共扫描 XX 个活跃模板)
  PH CTR 中位数: X.X%
  有 FTD 转化: X 个文案
  平均 ROI: X.X

💡 AI 点评:
  - Top 1 特征: [高分原因]
  - 衰减预警: [哪些模板在下降]
  - 本周趋势: [vs 上周对比]
```

## 与其他 skill 边界

```
bowjwj-send-analysis:  单次发送效果 (本 skill 是 3 天聚合排名)
bowjwj-template-evolution: 模板迭代/AI 生成 (本 skill 消费者, 输出衰减信号)
bowjwj-conversion-funnel:  实时转化查单 (本 skill 是每日静态快照)
bowjwj-daily-playbook:     晨报 (可引用本 skill 排名 top 3)
```

## 红线

- 不自带脚本以外的独立逻辑 (所有排名算法在 generate_ranking.py)
- 不跨 backend (只 NN33 ph)
- 不自动冻模板 (只输出排名, 由 frozen-manager 决策)
- PH IP 过滤必须执行 (不用 headline 原始 CTR)
- 样本 < 100 sent 的模板标注"样本不足"但不排除

## 依赖 skills

```
bowjwj-aicrm             API 地图 + JWT 凭据
bowjwj-conversion-funnel 共用 operations-report
bowjwj-template-evolution 模板维度互补
```
