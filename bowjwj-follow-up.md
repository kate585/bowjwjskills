---
name: bowjwj-follow-up
description: bowjwj 指数递增放量跟单协调器。Willy 说"跟单 #N"、"看跟单队列"、"确认 A #N"、"跟单状态"、"启动跟单 #N L0"时加载。按 1→5→10→20 包阶梯自动/半自动推进, 基于 replay-dashboard 业务口径判决。只协调, 真执行走 follow_up_engine.py。
---

# bowjwj-follow-up (跟单协调器)

## 何时触发

**启动**:
- "启动跟单 #N" (从 L0 开始)
- "跟单 #N" (新组合第一次跑)

**查看**:
- "看跟单队列" / "跟单状态"
- "跟单 #N 进度"
- "看 pending 建议"

**确认** (手批层级):
- "A #N"  / "确认 #N 进 L2"
- "N #N"  / "不跟 #N"
- "P24 #N" / "暂停 #N 24h"

## 策略: 4 层指数递增 (1→5→10→20)

| 层 | 包数 | 号码量 | 判决条件 | 自动? | 等待窗口 |
|----|------|--------|---------|-------|---------|
| L0 | 1 | 50-100 | click >= 3 | ⚙️ 自动 L1 | T+20min |
| L1 | 5 | 250-500 | click >= 10 或 CTR >= 2% | 🟡 建议 L2, Willy A 批 | T+20min |
| L2 | 10 | 500-1000 | click >= 20 或 reg >= 2 | 🟡 建议 L3, Willy A 批 | T+30min |
| L3 | 20 | 1000-2000 | ftd >= 1 | 💰 SUCCESS (常驻池) | T+2h |
| 未达 | - | - | - | 🧊 冻 24h + 降级冷却 | - |

## 数据与脚本 (已就位)

```
stats.db.follow_up_state     跟单状态机 (combo_id 主键)
  current_layer              L0/L1/L2/L3/SUCCESS/FROZEN
  current_round_id           正在跑的 round
  next_check_at              下次判决时间
  auto_advance               L0=1, 其他=0
  history_json               完整层级历史
  suggestion_pending         等 Willy 批 (1=是)

~/.hermes/state/bowjwj/follow_up_engine.py
  check_and_advance()         扫 due, 执行决策 (cron 每 5min 调)
  init_follow_up(...)         手动起 L0 (batch-send 后 hook)
  _send_layer(...)            发下一层 (通用)
  _pick_packs(n, carrier)     从 willy哥专用池挑包

cron:
  bowjwj-collect-batches (每 5min) 串联: 
    collect_batch → follow_up_engine → export
```

## TG 告警模板

### 自动推进通知 (L0→L1)
```
⚙️ [P2] #42 L0→L1 自动推进 (5包)
click=4 CTR=6.7%
approval <id>
```

### 建议批准 (L1→L2 / L2→L3)
```
🎯 [P1] #42 建议 L1→L2 · 回复 A 放量
sent=235 click=12 CTR=5.1% reg=3
next_packs=10 预算 ~$1.85
```

### 成功 (L3 FTD)
```
💰 [P1] #42 进入 SUCCESS · FTD 2 存款 ₱200
```

### 冻结 (未达标)
```
🧊 [P2] #42 L1 未达标, 冻结 24h
sent=245 click=1 CTR=0.4%
```

## Willy 命令处理 (AI 对话)

```
"A #68"        → 读 follow_up_state 找 pending, 调 _send_layer 进下层
"N #68"        → UPDATE follow_up_state SET current_layer='FROZEN', suspended_until=now+24h
"P24 #68"      → UPDATE suspended_until=now+24h, layer 不变
"启动 #199 L0" → follow_up_engine --init <combo_id> 199 L0 <new_round>
```

## 告警限频

```
单小时 follow-up 类 alert 上限: 3 条 (_recent_alerts_count 硬约束)
超过限制 skip 当前判决 (留到下一 cron 周期)
P0 不受此限 (SUCCESS / 系统错误例外)
```

## 与其他 skill 边界

```
bowjwj-batch-send:
  L0 可手动触发 batch-send, 后续层由 follow_up_engine 自动发
  batch-send 成功后应 call init_follow_up (hook 未实现, 当前要手动 init)

bowjwj-frozen-manager:
  未达标的 combo 本 skill 直接写 follow_up_state=FROZEN
  不重复调 frozen-manager (避免 2 个状态机打架)

bowjwj-conversion-funnel:
  L3 SUCCESS 后进入 "常驻放量池", 后续主力发送走日常放量 (不再跟单)
  本 skill 只管"探测→验证", SUCCESS 后交给日常 orchestration

bowjwj-alert-manager:
  本 skill 所有通知走 raise_alert
  单 combo 在 pending 状态时, 同 fingerprint 24h 去重

bowjwj-seq-orchestrator:
  本 skill 覆盖了其"Exploit 放量已知高 ROI" 的部分职责
  seq-orchestrator 专注"Explore 新组合", follow-up 专注"已测的放量路径"
```

## 关键教训 (踩过的)

1. **阈值要归一化**: 50 条包 click=3 是 6% 极好, 100 条包 click=3 才 3% 一般
   → 规则用 `click >= N OR CTR >= X%` 双判, 别只看绝对数

2. **后台数据延迟**: replay-dashboard 60s cache, send-log 实时, FTD T+24h 才稳
   → L3 判决窗口必须 >= 2h, 不然 FTD 漏判
   → ⚠️ 当前 L3 check_after_min=120 已经是最低, 实战可能要 T+6h

3. **#68 实测 ROI 3.53 但 T+9h 才出 FTD**: 业务反应慢, 跟单系统判决点不能太早
   → 这就是为啥 L3 最少 2h, L4 若加要 24h

4. **自动推进 L0→L1 风险可控**: 1 包 $0.28 + 5 包 $1.4 = 单组合最大 $1.7 失控
   → 继续自动, 但 L1→L2 开始必须人批 (10 包 $2.8 起跳)

5. **同组合短期重发疲劳**: 实战 #67 T+15min 和 T+30min click 量没增长, 说明前 30min 是黄金反应期
   → 判决窗口贴近黄金期合理

6. **willy哥专用 Smart 都是 50 条包**: 没有 100 条包, 总号码量比预期少一半
   → L3 20 包 = 1000 条不是 2000, 要通知 Willy 若要大放量考虑别的料源

## 查询队列 (AI 对话现读 DB)

```sql
-- 当前所有跟单
SELECT seq, current_layer, next_check_at, suggestion_pending,
       json_extract(history_json, '$[#-1]') latest
FROM follow_up_state 
ORDER BY updated_at DESC;

-- 待批准清单
SELECT seq, current_layer FROM follow_up_state 
WHERE suggestion_pending=1;

-- 成功 combo
SELECT seq FROM follow_up_state WHERE current_layer='SUCCESS';

-- 冻结中
SELECT seq, suspended_until FROM follow_up_state 
WHERE current_layer='FROZEN' AND datetime(suspended_until) > datetime('now');
```

## 不做的事

- ❌ 不自动推进 L1→L2+ (必须 Willy 批准, 金额上去风险大)
- ❌ 不自动放量 SUCCESS 后的"常驻池" (交给日常 orchestration)
- ❌ 不覆盖用户手动决策 (Willy 说 N 停就是停, 不二次推荐)
- ❌ 不短时间重推相同 combo (24h 冷却)
- ❌ 不跨 backend (只 NN33 ph)
- ❌ 告警不刷屏 (限频 3/h, P0 例外)

## 依赖

```
bowjwj-aicrm             API 地图 + replay-dashboard 真相源
bowjwj-batch-send        L0 手动触发的执行层
bowjwj-conversion-funnel 数据查询底座 (SUCCESS 后转给它)
bowjwj-alert-manager     TG 告警通路
```