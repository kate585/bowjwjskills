---
name: bowjwj-data-sourcing
description: bowjwj 料子采购/质量追溯协调器。Willy 说"录料子采购"、"料子质量"、"供应商 ROI"、"某来源的料效果"、"料子衰减曲线"时加载。后台 categories API 给 source 聚合, 本地 stats.db 补采购单价/供应商/质量分 (后台没这些字段)。只协调, 脚本最小。
---

# bowjwj-data-sourcing (协调器, 本地落库型)

## 何时触发

**录入**:
- "录料子采购: 银河 4 月 23 号, 单价 0.003U, 数量 5000"
- "打标 <source关键词> 供应商=龙少"
- "这批料是 <supplier> 的"

**查询**:
- "供应商 ROI 排行"
- "来源 X 的料效果"
- "料子衰减曲线" / "这批跑了几次"
- "质量分排行"

**巡检**:
- "本周采购消耗/产出"
- "哪个供应商 ROI 最高"

## 为什么要落库

```
后台只有 source (字符串自由填) + cleanCount + createdAt
后台没有:
  ❌ 采购单价 (USDT/条)
  ❌ 供应商标签 (谁给的)
  ❌ 质量评分 (跑过后的反馈)
  ❌ 衰减记录 (同源多次跑 CTR 变化)

→ 本地 stats.db 补这 4 类字段, 按 source key 关联.
```

## 数据源

### 线上 (刀 1): `/api/phone-packs/categories`

```
GET /api/phone-packs/categories?backendInstanceId=<BID>
返回每个 source 聚合:
  key / title / packCount / totalCleanCount / latestCreatedAt

作用: 拿 source 清单 (当前 NN33 ph 20 个分类)
```

### 线上 (刀 2): `/api/phone-packs` (明细)

```
GET /api/phone-packs?source=<key>&pageSize=500
拿该 source 下所有 pack_id + cleanCount + packIndex 等
用于"这批料跑了几次"反查
```

### 线上 (刀 3): `/api/operations-report` (效果)

```
GET /api/operations-report?createdByUserId=<我>&groupBy=campaign
对每 campaign 查 phonePackId → 反查 source → 聚合 source 级 FTD/ROI
```

### 本地 stats.db 新表 (这部分要落库)

```
-- 采购记录
CREATE TABLE IF NOT EXISTS pack_sourcing(
  id INTEGER PRIMARY KEY,
  source_key TEXT,                       -- 匹配 categories.key
  supplier TEXT,                          -- 供应商标签 (龙少/白羊/银河/willy自己/...)
  supplier_contact TEXT,                  -- 联系方式 (qun号, 可选)
  purchase_date TEXT,                     -- 采购日期
  unit_price_usdt REAL,                   -- 单价 USDT
  total_numbers INTEGER,                   -- 采购数量
  total_cost_usdt REAL,                   -- 总成本 (= unit * total)
  carrier_mix TEXT,                        -- Smart/Globe/DITO 比例 (JSON)
  notes TEXT,                              -- 备注 (质量/黑名单情况 等)
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 质量反馈 (每次跑完累计)
CREATE TABLE IF NOT EXISTS source_quality(
  source_key TEXT PRIMARY KEY,
  total_rounds INTEGER DEFAULT 0,
  total_sent INTEGER DEFAULT 0,
  total_click INTEGER DEFAULT 0,
  total_register INTEGER DEFAULT 0,
  total_ftd INTEGER DEFAULT 0,
  total_deposit_php REAL DEFAULT 0,
  total_sms_cost_php REAL DEFAULT 0,
  ctr REAL,                               -- 计算列
  ftd_rate REAL,
  roi REAL,                               -- netProfit / sms_cost
  quality_score INTEGER,                   -- 0-100, AI 算 + Willy 手调
  first_used_at TEXT,
  last_used_at TEXT,
  decay_curve_json TEXT                    -- [{round:1, ctr:4.2}, {round:2, ctr:3.1}, ...]
);
```

## 视图组装

### 1) 录采购 "录料子: 银河 4 月 23 号, 单价 0.003U, 5000 条, 供应商=银河"

```
AI 解析自然语言 → 结构化字段:
  source_key: 匹配 categories 找到 "银河4月23号数据" 开头的 key (可能多个, 让 Willy 选或填 ALL)
  supplier: "银河"
  unit_price_usdt: 0.003
  total_numbers: 5000
  total_cost_usdt: 15
  
INSERT INTO pack_sourcing(...)
确认: "已录 1 条, 采购成本 $15, 源自 5 个 category key"
```

### 2) 供应商 ROI 排行 "供应商 ROI 排行"

```
1. JOIN pack_sourcing + source_quality
2. GROUP BY supplier
3. 计算:
   - 总采购 $ (sum(unit_price_usdt * total_numbers))
   - 总 sms 成本 $ (sum 从 source_quality)
   - 总收入 $ (sum deposit - withdraw)
   - 综合 ROI = (收入 - 采购 - sms成本) / 采购

排行表:
  供应商 · 采购 $ · 运营 $ · 收入 $ · 综合 ROI · 包数 · 平均质量分
```

### 3) 某来源效果 "看 银河4月23 这批料"

```
1. pack_sourcing 查 supplier='银河' AND source_key LIKE '银河4月23%'
2. source_quality JOIN 拿 CTR/FTD/ROI
3. phone-packs?source=xxx 拿剩余可用
4. 推断: "这批共采购 N 条, 跑了 M 次, 剩 K 条, 综合 ROI X"
```

### 4) 衰减曲线 "某源的衰减曲线"

```
source_quality.decay_curve_json 已存
解析 → 输出:
  第 1 次跑 (2026-04-22): CTR 4.2%
  第 2 次跑 (2026-04-23): CTR 3.5% (-16%)
  第 3 次跑 (2026-04-24): CTR 2.1% (-40%)
  → 趋势: falling, 不建议再跑
```

### 5) 反向打标 (定时任务, 这个可能要脚本)

```
每次 round 完 (hook):
  → 拿 campaign.phonePackId → phone-pack.source
  → source_quality 累加 sent/click/register/ftd/cost
  → decay_curve 追加 {round: N, ctr: X}
  → 重算 quality_score = f(roi, ctr_weight, ftd_weight)
  
这步需要极小脚本 (接 bowjwj_log.verdict hook), AI 现场写不靠谱.
```

## 判定阈值

| 指标 | 阈值 | 动作 |
|------|------|------|
| 综合 ROI < 0 | sold_numbers >= 500 | 红 亏本供应商 |
| 综合 ROI > 3 | sold_numbers >= 500 | 绿 优质供应商 |
| 衰减 > 50% | rounds >= 3 | 黄 停用该 source |
| quality_score > 80 | rounds >= 3 | 绿 优质 |
| quality_score < 40 | rounds >= 3 | 红 低质 |

## 与其他 skill 边界

```
bowjwj-pack-health-monitor (s10):
  兄弟 skill, 关注"库存健康" (还剩多少可用)
  本 skill 关注"来源质量" (买得值不值)
  
bowjwj-conversion-funnel:
  提供 FTD/ROI 数据源, 本 skill 按 source 聚合

bowjwj-frozen-manager:
  本 skill 产 "供应商级红告警" → 建议弃用该 source 所有包
```

## 脚本 (唯一要落地的)

```
~/.hermes/state/bowjwj/source_quality_hook.py
  被 bowjwj_log.verdict() 最后一步调, 专门更新 source_quality
  ≈ 50 行, 纯 DB 读写
```

## 已知坑

1. **后台 source 字段太随意**: 别人录的"银河4月23 - Smart yo家黑名单 63918" 和 "银河4.23 Smart" 是同批料两种写法, 需要 supplier 标签兜底
2. **category key 可能包含黑名单标记**: "yo家黑名单" 要分开算, 别混入 source_quality
3. **同 source 多次跑的"第几次"**: 按 round_id 时间排序, 不是 pack 级
4. **运营商比例**: carrier_mix 要 AI 或 regex 解析 name 推断 (Smart/Globe/DITO)
5. **采购时区**: Willy GMT+8, purchase_date 用本地日期
6. **采购金额单位**: 存 USDT, 显示时可 × 57 转 PHP 或 × 1 显 USD
7. **Willy 可能忘录**: 新上传的料子要提醒 "刚看到 N 个新 source, 要录采购吗?"
8. **质量分 quality_score**: 不是绝对值, 是相对其他 source, 需要样本 >= 3 rounds 才准

## 红线

- 不自动删 source (后台数据)
- 不自动补采购信息 (猜单价出问题)
- 脚本只 1 个 (source_quality_hook.py), 别蔓延
- 不跨 backend
- 每次采购录入要 Willy 确认 (AI 解析后问 "对吗?")

## 依赖 skills

```
bowjwj-aicrm             phone-pack API
bowjwj-conversion-funnel operations-report 共用
bowjwj-pack-health-monitor 兄弟
bowjwj-frozen-manager    消费告警
bowjwj-auto-campaign     verdict hook 触发本 skill 反向打标
```
