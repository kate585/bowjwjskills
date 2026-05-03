---
name: bowjwj-conversion-funnel
description: bowjwj 转化漏斗查询协调器。**任何时候** Willy 说"看 FTD"、"看注册效果"、"ROI 多少"、"看今天赚了多少"、"看代理线效果"、"看 batch 效果"、"转化漏斗"、"#68 真实转化"时加载。走 /api/operations-report (支持 createdByUserId / agentLineId / groupBy) 拿真 FTD 数据, 配合 /api/intelligence/dimensions 看市场基线。只协调, 不自带脚本。
---

# bowjwj-conversion-funnel (协调器)

## 何时触发

**单 batch / campaign 钻取**:
- "seq68 真实转化"
- "看 BATCH-74f5a38e 效果"
- "#68 FTD"

**时段汇总**:
- "今天赚了多少" / "本周 ROI" / "最近 7 天注册"
- "昨天我发了啥 FTD 咋样"

**维度排名**:
- "代理线排名"
- "哪个 batch FTD 最多"
- "按创建人分" (多人运营时)

**市场对比** (基线):
- "我 vs 全系统 CTR 对比"
- "标杆通道 ROI"
- "学学高转化模板"

## 协调目标

**薄协调层**, 不写 shell/py, AI 现场拼 HTTP 调用 + 格式化输出. 所有真实转化数据来自后台, 本地 stats.db 只追 send 层. 本 skill 是从"发多少"到"赚多少"的桥梁.

## 数据源 (重构后)

### 主: 本地 `stats.db.batches` 表

所有 replay-dashboard 字段都落库了, 直接 SQL 聚合, 毫秒级.

```sql
-- "今天赚了多少" 
SELECT SUM(success_count) sent, SUM(clicks) click, SUM(uv) uv,
       SUM(registrations) reg, SUM(ftd_count) ftd,
       SUM(deposit_amount) deposit, SUM(valid_betting_amount) vb,
       SUM(net_pnl_amount) pnl, SUM(sms_cost) cost
FROM batches WHERE DATE(sent_at) = DATE('now');

-- "seq68 真实转化"
SELECT * FROM batches WHERE seq=68;

-- "ROI > 1 的爆款"  
SELECT seq, tpl_name, ch_name, ai_roi, deposit_amount, ftd_count
FROM batches WHERE ai_roi > 1 ORDER BY ai_roi DESC;

-- "代理线排名"
SELECT agent_line_name, COUNT(*) batches,
       SUM(registrations) reg, SUM(ftd_count) ftd, SUM(deposit_amount) dep
FROM batches WHERE sent_at > datetime('now', '-7 day')
GROUP BY agent_line_name ORDER BY dep DESC;
```

刷新: `python3 ~/.hermes/state/bowjwj/collect_batch.py --latest` 之前查询一次.

### 辅: 线上 `/api/operations-report` (跨 batch 聚合 + 延迟数据)

用于:
- 多天汇总 (用 summary 字段)
- operations-report 有 T+N snapshot (FTD 后填), 本地 batches 没的补
- 延迟 30min-1h, 不是实时

### 辅: 线上 `/api/intelligence/dimensions` (市场基线)

看全系统 Top N 做基线对比. 个人筛不了.

## 关键字段 (已落本地)

| 层 | 字段 |
|----|------|
| 发送 | success_count (sent 口径唯一真相) |
| 流量 | raw_clicks (含 bot) vs clicks (去 bot) vs uv |
| 转化 | registrations · ftd_count · ftd_amount · deposit_amount · valid_betting_amount |
| 漏斗 | ctr · click_to_reg_rate · reg_to_ftd_rate · end_to_end_rate |
| 质量 | new_visitor_rate · pv_uv_ratio · betting_multiplier |
| 成本 | sms_cost · cost_per_registration · cost_per_click_uv |
| AI | ai_roi · health_score · ai_prompt_summary |
| 对比 | trend (mixed/rising/falling) · baseline_json |

## 两刀分工

| 场景 | 用哪刀 |
|------|--------|
| "我的 FTD 多少" | 刀 1 (operations-report + createdByUserId=我) |
| "#68 转化漏斗" | 刀 1 (groupBy=campaign, 找 batchId 匹配) |
| "代理线排名" | 刀 1 (groupBy=agent) |
| "哪个通道 ROI 高 (全系统)" | 刀 2 (intelligence smsChannel) |
| "学学高转化模板" | 刀 2 (intelligence textCopy, rank 1-5) |
| "我今天 vs 基线" | 两刀对比 |

## 默认查询流程 (AI 对话式, 不写脚本)

### 1) `#68 真实转化` (单 batch)

```
1. stats.db 查 combo_coverage WHERE seq=68 → 拿 round_id
2. 读 ~/.hermes/state/bowjwj/rounds/<round_id>/step1_test_send_response.json
   → 拿 campaignBatchId (BATCH-xxx)
3. GET /api/operations-report?
     backendInstanceId=c7ee7c4c
     createdByUserId=ec7fbe8c-3a0e-4823-b1da-0afc88c76f89
     dateFrom=<round+日期>
     dateTo=<round+2天>
     groupBy=campaign
4. 从返回 items 里找 batchId 匹配
5. 展示完整 10 字段漏斗
```

输出模板:
```
🎯 #68 真实转化 (seq68-20260424-0646)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BATCH-74f5a38e-babf-46f0-ae2e-da2381986846
模板: 大官人加白 2 × 通道: 九 LuckyPlay S

漏斗:
  发送      200
  点击        2  (CTR 1.0%)
  UV         2  (独立访客)
  注册      2  (注册率 100%!)  ⭐ 关键发现
  FTD        0  (首充暂无)
  存款      0
  
成本:
  SMS 成本    ₱ 28.35 ($0.51)
  每注册成本   ₱ 14.17
  每首充成本   N/A (0 FTD)

ROI:       0 (未回本, 待 FTD)
基线对比: 全系统平均 smsChannel CTR 4.14% → 你 1.0% 低于基线
```

### 2) `看今天赚了多少` (时段)

```
1. GET /api/operations-report?
     createdByUserId=我
     dateFrom=today dateTo=today
     groupBy=date
2. 拿 summary + 1 行 date 聚合
3. 对比昨天
```

### 3) `代理线排名`

```
1. GET /api/operations-report?
     createdByUserId=我  
     dateFrom=7d_ago
     groupBy=agent
2. 按 ftdCount / roi 排序
3. Top 5 + Bottom 5
```

### 4) `学学高转化模板` (市场)

```
1. GET /api/intelligence/dimensions?period=7d
2. textCopy 取 rank 1-10
3. 过滤 ftdRate > 10% && campaignCount >= 5 (样本足)
4. 显示 dimensionLabel + 雷达 + tags
5. 推荐: "抄这几个文案的结构特征"
```

## 关键字段字典 (别搞混)

| 字段 | 定义 | 来自 |
|------|------|------|
| sentCount | 批次 target (包 cleanCount) | operations-report |
| success_count | 实发成功 (SMPP 投递成功) | send-log |
| delivered (intel) | 同 success_count | intelligence |
| clicks | 点击数 (含 bot) | operations-report |
| uv | 独立访客 (去 bot) | operations-report |
| registrations | 注册数 | operations-report |
| ftdCount | 首充人数 | operations-report |
| ftdRate (intel) | ftdCount / registrations | intelligence, 注册转 FTD 率 |
| depositAmount | 存款总额 | operations-report |
| commission | 佣金 | operations-report |
| netProfit | 净利润 | operations-report |
| roas | Revenue / AdSpend | operations-report |
| roi | Return / Cost | operations-report |

## 两个 CTR 口径 (必须说清)

```
后台 CTR 分母 = sentCount (包 target)
  #68: 2 / 200 = 1.0%

我自己算 CTR 分母 = success_count (实发)  
  #68: 2 / 135 = 1.48%

运营看"投放效率"用前者 (和钱挂钩)
技术看"通道质量"用后者
默认用后者 + 备注后台口径
```

## period 参数语义

```
触发词映射:
  "今天"        → dateFrom=today dateTo=today
  "昨天"        → dateFrom=yesterday dateTo=yesterday
  "最近 7 天"   → dateFrom=now-7d dateTo=today
  "上周"        → dateFrom=Mon-13d  dateTo=Sun-7d
  "本月"        → dateFrom=1st dateTo=today
  "30 天"       → dateFrom=now-30d dateTo=today
  
限制: 单次 <= 90 天 (系统硬顶)
```

## ⚠️ 已知坑

1. **intelligence/dimensions 筛不了个人**, 只能看全系统 — 别问 "我的通道排名" 找那 API
2. **60s cache** 这边生效, --forceRefresh 只 intelligence 支持, operations-report 不支持刷, 等 1 分钟
3. **ftdCount 统计窗口** 后台是 T+N 的 snapshot, 新发的 campaign 可能要等 24h FTD 才落账, 别急
4. **sentCount vs success_count 口径** 后台报表用 sentCount (= target), 和 send-log successCount 差 dedup
5. **depositAmount / withdrawAmount 单位是 PHP** (菲律宾比索), 转 USD 要 × 0.018
6. **agentLineId 是运营报表主键**, 不是 campaign 主键, 1 campaign 1 agentLine
7. **"商户佣金"和"净利润"口径**: netProfit = deposit - withdraw - smsCost - commission (源码逻辑)
8. **0 FTD 不代表失败**, 首充可能发后 7-30 天才来 (尤其博彩用户), 要观察 T+30

## 结果解读模板 (AI 用)

```
单 batch:
  CTR < 0.5%  → "通道/文案质量差, 建议冻"
  CTR 0.5-2%  → "中等, 跑 2 轮看稳定性"
  CTR > 2%    → "达标, 但看注册率"
  注册率 > 3% 且 FTD > 0 → "⭐ 放量候选"
  CTR 好但 注册 0 → "短链跳转有问题 / 落地页差"
  注册多但 FTD 0 且 T+3 天了 → "用户质量低 (僵尸号?)"
```

## 触发后第一问 (意图不明时)

```
你要看哪个维度?
  A. 单 batch/seq 详情      (给 seq 或 batchId)
  B. 时段汇总                (给 period: 今天/7d/30d)
  C. 某代理线 / 某通道      (给 id)  
  D. 市场标杆               (看全系统 Top N)
```

## 红线 (不做的事)

- ❌ 不自带 python/bash 脚本
- ❌ 不落库 (operations-report 数据有后台, 不重复, 实时查就好)
- ❌ 不做自动放量建议 (只展示数据, 决策由 Willy)
- ❌ 不试改 FTD 归因口径 (信任后台统计)
- ❌ 不查 agentLine 系统创建, 不建不删
- ❌ 不跨 backend (只 NN33 ph, backendInstanceId 硬编码)
- ❌ 不 aggregate 超过 90 天 (系统限制)

## 依赖 skills

```
bowjwj-aicrm          - API 地图 (send-log 在这)
bowjwj-send-analysis  - 送达层分析 (本 skill 是其上层)
bowjwj-batch-send     - 批量发起

本 skill 回答:
  "我这批发出去, 真赚钱了吗?"
```
