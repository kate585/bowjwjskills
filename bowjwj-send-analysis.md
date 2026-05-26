---
name: bowjwj-send-analysis
description: bowjwj 发送效果查询协调器 (重构后)。Willy 说"看 #68 效果"/"看 BATCH-xxx"/"看今天效果"/"看九 LuckyPlay 通道"/"所有 zero_click"时加载。主数据源 = `batches` 表 (本地, 由 replay-dashboard 填充), 辅助 intelligence/dimensions。**不要再用 send-logs/visits 作主源**, 它们是技术分层数据, 业务口径用 replay-dashboard 的 batches。纯协调, 脚本已分离到 collect_batch.py。
---

# bowjwj-send-analysis (协调器)

## 新后台覆盖规则 (2026-05-26)

本节优先于后面的旧规则。

- Base URL: `https://aicrm.bo-pro.cc`
- 必带 header: `Authorization: Bearer $JWT` 和 `X-AICRM-Tenant: aicrm-default`
- API 字典：`GET /api/_meta/endpoints?module=replay-dashboard|operations-report|metrics|send-logs`

### 数据口径优先级

业务复盘仍以 replay-dashboard 为主：

```text
GET /api/replay-dashboard/batches
GET /api/replay-dashboard/batches/:batchId
GET /api/replay-dashboard/batches/:batchId/packs/:packId
GET /api/replay-dashboard/batches/:batchId/dimensions
```

新后台新增 metrics v2，适合做时段汇总、驾驶舱、指标解释：

```text
POST /api/metrics/query
GET  /api/metrics/freshness
GET  /api/metrics/explain
POST /api/metrics/export-jobs
POST /api/metrics/recompute-jobs
```

常用 metric keys：

```text
send_target_count
submit_success_count
submit_failed_count
dlr_delivered_count
click_pv
click_uv
registration_count
ftd_count
cost
```

汇报规则：

- 单 batch / 单 seq：优先 replay-dashboard。
- 今日/近 N 天总览：优先 metrics v2；必要时用 operations-report 校验营收/FTD。
- 发送失败和去重：send-logs 是技术口径，只作辅助。

## 何时触发

**单次查询** (按 seq / campaign / session):
- "看 #68 效果" / "#68 CTR" / "#68 详情"
- "看 campaign d130c027" / "session 8902c1e4"

**时段汇总** (按时间范围):
- "看今天效果" / "最近 24h" / "最近 7 天 CTR"
- "今早发了啥"

**筛选聚合** (按维度):
- "看九 LuckyPlay 通道效果"
- "大官人加白 3 所有组合效果"
- "Smart 侧 CTR 排行"
- "所有 zero_click 的组合"

## 协调目标

本 skill 是薄协调层, **不写 shell/py 脚本**, AI 现场读本地 DB + 必要时拉线上, 文字输出. dashboard "组合矩阵" tab 已经是可视化兜底, 本 skill 专攻"对话式精确查询".

## 数据源 (重构后统一)

### 主数据源: 本地 `stats.db.batches` 表 (66 列完整版)

由 `collect_batch.py` 从 `/api/replay-dashboard/batches/<batchId>` 同步.
字段含:
- 发送层: target/success/dedup/failed
- 流量层: raw_clicks/clicks/uv/pv/ip_count/ctr/new_visitor_rate/pv_uv_ratio/ip_uv_ratio
- 转化层: registrations/ftd_count/ftd_amount/deposit/withdraw/valid_bet/pnl + 漏斗各率
- 成本层: sms_cost/cost_per_uv/cost_per_reg
- 评分: health_score/ai_roi + pack_score
- 对比: baseline_json/delta_json/trend
- AI: ai_prompt_summary (完整文本) / ai_analysis_json (top/bottom packs)
- 拆分: source/region/ua/hourly breakdown JSON
- 窗口: window_label (72H) / start / end

### 辅助: `/api/intelligence/dimensions`

只用于"市场基线 / 全系统 Top N" 参考 (非 Willy 自己).

### 触发采集

```
python3 ~/.hermes/state/bowjwj/collect_batch.py --latest         # 最新 round
python3 ~/.hermes/state/bowjwj/collect_batch.py --all-open       # 所有 round
python3 ~/.hermes/state/bowjwj/collect_batch.py --batch <bid>    # 单 batch
```

**每次 Willy 问"效果"前先自动跑一次 collect_batch --latest**, 再查本地.

### 🤖 5min cron 自动采 (2026-04-24 配置)

```
job_id: d0313f9a8a14
schedule: every 5m
deliver: local (静默, 异常才 raise alert)

行为:
  1. collect_batch.py --all-open  (所有 round, 含未收敛的)
  2. export.py 刷 data.json
  3. JWT 401 → P0 TG
  4. 新 ROI>2 爆款 → P1 TG
```

管理命令:
```
cronjob(action='list')                                                管理面板
cronjob(action='pause', job_id='d0313f9a8a14')                        暂停
cronjob(action='resume', job_id='d0313f9a8a14')                       恢复
cronjob(action='update', job_id='d0313f9a8a14', schedule='every 10m') 改频率
```

**所以 AI 回答 "效果" 时**:
- 如果 cron 正常跑 (next_run_at 在未来), **本地 batches 表数据新鲜**, 不用现采, 直接查
- 如果 last_status='error', 或 > 10min 无更新, 才手动跑 collect_batch

## 典型查询 (SQL 片段)

```sql
-- 单 seq 效果
SELECT * FROM batches WHERE seq=68 ORDER BY last_refreshed_at DESC LIMIT 1;

-- 今日全量
SELECT SUM(success_count) sent, SUM(clicks) click, SUM(registrations) reg,
       SUM(ftd_count) ftd, SUM(deposit_amount) dep, AVG(ai_roi) avg_roi
FROM batches WHERE DATE(sent_at) = DATE('now');

-- 某通道效果
SELECT seq, tpl_name, success_count, clicks, registrations, ftd_count, ai_roi
FROM batches WHERE ch_id='165b9ca3-...' ORDER BY last_refreshed_at DESC;

-- 高 ROI 组合 Top
SELECT * FROM combo_coverage 
WHERE total_ftd > 0 OR last_ai_roi > 1
ORDER BY total_deposit DESC, last_ai_roi DESC;
```

## 默认查询路径 (Q1-Q4 按默认)

### 1) 单次 `#68 效果`

```
步骤 (AI 对话里走, 不写脚本):
  1. stats.db SELECT from combo_coverage WHERE seq=68
  2. JOIN sessions WHERE tpl_id AND sms_id (拿该组合所有 round session)
  3. 按 round_id desc 列每次投递:
     - send-log 层: target/success/dedup/sentAt/adapter
     - 访客层:     clickCount / bot_count
     - verdict:     passed / rejected / zero_click
  4. 组合累计行: tested_rounds / total_sent / total_click / CTR
  5. 和全 Smart 侧平均对比一行
  6. 如果用户带 --refresh, 用 db.fetch_send_log_for_campaign(cid) 重拉校准
```

输出模板:
```
🎯 #68 Smart · 大官人加白2 × 九 LuckyPlay S
──────────────────────────────────────────────
round batch-20260424-0646-seq68   (2026-04-24 06:47 BJ)
  📤 投递: target=135  success=135  dedup=65   pack=200
  👆 点击: 2 真实 (mobile 2/2) + 7 bot  CTR=1.48%
  verdict: passed (below_threshold_3)

累计 (rounds=1): sent 135 · click 2 · CTR 1.48%

💡 对比: Smart 侧组合平均 CTR 约 2.3% (基线未定, 仅 2 组合样本)
```

### 2) 时段 `看今天效果` / `最近 24h`

```
步骤:
  1. stats.db 拉 rounds WHERE started_at >= cutoff
  2. 聚合 sum(sent) / sum(click) / count(distinct combo)
  3. 按 verdict 分布
  4. 如果带 --refresh: GET /api/dashboard/user-metrics 今日总览
  5. Top 3 组合 (按 CTR), Bot 3 组合 (0 click 可疑)
```

### 3) 筛选 `看九 LuckyPlay 通道效果`

```
通道名模糊 → pool.json 找 ch_id
→ SELECT * FROM combo_coverage WHERE ch_id=... AND tested_rounds>0
→ 按模板列所有组合 + 该通道 total 发送/点击
→ 推荐: 该通道 CTR 最高模板是哪个
```

### 4) verdict 筛选 `所有 zero_click 的组合`

```
SELECT seq, combo_id, tpl_name, ch_name FROM combo_coverage 
WHERE last_verdict LIKE '%zero_click%' OR (tested_rounds>0 AND total_click=0)
```

## 🎯 标准监测脚本 (不自创, 用 monitor.py)

**2026-04-24 固化**: 每次"查监测"都跑 `python3 ~/.hermes/state/bowjwj/monitor.py --latest` 或 `monitor.py <round_id>`, 它自动:

```
拉: campaigns/{cid} + send-logs + shortlinks/visits + replay-dashboard/batches
落: sessions (含 replay_clicks/reg/ftd + agent_line + batch_id)
    polls (每次监测快照, 能画时间线)
    shortlink_visits (访客明细, 能追 IP)
    combo_coverage (refresh 覆盖率)
输出: 文字报表 target/sent/click/bot/reg/ftd 六列
```

**以前踩的坑** (2026-04-24):
- 每次现查不落库 → 数据过眼云烟, 要重拉
- 只看 shortlinks/visits → 漏 reg/ftd, 向 Willy 汇报错数据
- 每次手写 sqlite UPSERT → 容易忘字段

**纪律**: 想说"让我监测一下" 就直接 `monitor.py`, 别自己拼 curl。

## 🔀 技术 vs 业务口径必须分清 (血泪 2026-04-24)

| 问题 | 用哪个口径 |
|------|-----------|
| "发了多少" | send-log.successCount (技术) |
| "被点多少次" | shortlinks/visits 非 bot (技术) |
| "有多少真用户注册" | replay-dashboard registrations (业务) |
| "赚了多少" | operations-report ftd/deposit (业务) |
| "这个 batch 咋样" (业务汇报) | replay-dashboard/batches/{bid} 一把梭 |

**规则**: 向 Willy 汇报效果 = 业务口径为主, 技术口径为辅 (放备注)。
batch10 事件: 最初报 "3 点击 0 注册", 实际是 "3 点击 10 注册", 差距就是这个口径差。

## 关键字段映射 (别搞混)

| 概念 | 字段 | 出处 |
|------|------|------|
| 真实发送数 | `success_count` | send-log 层, 不是 cleanCount / targetCount |
| 真实点击 | shortlink visits 里 `isBot=false` 计数 | 别用 clickCount 如果它不准 |
| session clickCount | 后台已去 bot | 大多数情况等于 shortlink 真实点击 |
| CTR | `click / success_count` | 不是 /targetCount 不是 /cleanCount |
| dedup 率 | `dedup_skipped / (success + dedup)` | 做质量指标, 包大则 30%+ |

## --refresh 开关语义

```
默认: 纯 stats.db 读 (0.02s)
--refresh: 对查询涉及的 campaign 逐个拉 send-log 校准 sent/dedup
  * 每 campaign 1 个 HTTP 调用
  * 别一次性 --refresh 50+ 组合 (会慢 + 可能被系统限流)
  * AI 要在 --refresh >10 时先问 Willy 确认
```

## ⚠️ 已知坑 (2026-04-24 实测)

### 1. 短链域名可用性必查

`customShortlinkDomainConfigIds` 传了 5 个域名, 系统轮询挑. **某些域名可能挂了 (超时 / 被墙 / 被封)**, 导致相应 campaign 的用户点击打水漂.

判断方法 (每次发信前 + 每次效果差时都该查):
```bash
# 对每个域名 curl -I 看 302 或超时
for domain in vipbonus.vip now.vip claimbonus.vip bonusfast.xyz startbn.xyz; do
    code=$(curl -sS -o /dev/null -w "%{http_code}" -m 5 "https://$domain/test")
    echo "$code  $domain"
done
```

踩坑案例 (seq68-release-0911):
- 19 campaign 用 5 个域名轮换, `now.vip` 超时, 4 个 campaign 全 0 点击
- 18/19 组合 0 点击, 一度以为是料子问题, 实际是域名问题

诊断流程 (效果差时必跑):
1. **发送是否成功** → 查每个 campaign 的 `send-logs` (target=success 说明 SMPP 投递了)
2. **短链是否可达** → curl 每个域名, 看 302 还是 timeout
3. **访客数量** → `/api/shortlinks/{slid}/visits` 看 bot + real
4. **料子质量** → 对比历史同组合的 CTR 基线

### 2. 每 batch 1 reg 是系统伪信号

新建 agent_line 默认带 1 个"系统账户", 不是真用户注册.
**判业绩时 reg >= 2 才算真, ftd >= 1 才是金标准**.

### 3. visits 口径 vs replay 口径

- `/api/shortlinks/.../visits`: 技术层点击流水 (含 bot, 只点击无注册)
- `/api/replay-dashboard/batches/`: 业务层漏斗 (含 reg/ftd, 延迟 60s)
- **业务口径主源用 replay**, visits 只 debug IP/UA

### 4. 短链回流速度

原版 #68 T+5min 就有 3 real click, 放量版 T+30min 才 1 click. 
菲律宾用户典型回流: 5-30min 主要点击, 1-6h 注册, 6-24h FTD.
**判决窗口至少 T+30min 看 click, T+2h 看 reg, T+24h 看 ftd**. 别太早下 verdict.

---

- ❌ 不自带脚本 (AI 对话现读现算, 保持协调器干净)
- ❌ 不做 "自动生成可视化" (dashboard 已有组合矩阵)
- ❌ 不跨 backend (只 NN33 ph)
- ❌ 不改 stats.db 结构 (这是数据库的责任, 协调器只读)
- ❌ 不做 "建议放量/冻结" (那是 bowjwj-auto-campaign 的活)

## 依赖 skills

```
bowjwj-aicrm          — send-log 真相源规则写在这里 (⚠️ 章节)
bowjwj-auto-campaign  — 单轮闭环规则
bowjwj-batch-send     — 批量发起规则

本 skill 只查, 不发 — 分工清楚
```

## 触发后给 Willy 的第一问

如果查询意图模糊, AI 主动问:
```
查什么维度?
  A. 单次 (给我 seq / campaignId)
  B. 时段 (今天 / 24h / 7 天)
  C. 筛选 (某通道 / 某模板 / 某 verdict)
```

不猜, 按 Willy "澄清式" 偏好走.
