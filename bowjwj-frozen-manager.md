---
name: bowjwj-frozen-manager
description: bowjwj 冻结池管理协调器。**任何时候** Willy 说"冻 #N"、"解冻 #N"、"看冻结池"、"看 suspect"、"永冻 #N"、"刷新冻结判定"、"哪些组合该冻"时加载。按 click + FTD 双信号判 severity, 组合/通道/模板三层粒度, 半自动: 跑完 round AI 提议, Willy 批准后写入。只协调, 不自带脚本。
---

# bowjwj-frozen-manager (协调器)

## 何时触发

**查询**:
- "看冻结池" / "看 suspect"
- "哪些组合该冻"
- "#67 冻结状态"
- "通道 九 LuckyPlay 冻了吗"

**提议 / 执行**:
- "刷新冻结判定" (跑完一批后重新评估)
- "冻 #67" / "永冻 #120" / "解冻 #N"
- "冻 九 LuckyPlay 通道" (通道级)
- "冻 大官人加白 2 模板" (模板级)

**巡检**:
- "解冻到期了谁" (冷却期满需要放出来重试)
- "本周该升级永冻的"

## 协调目标

**薄协调层**, 判定规则写死在 skill, 操作本地 `policy.json` + `stats.db.combo_coverage`. 不自带脚本, AI 对话现场执行.

## 状态机

```
            ┌─────────┐
            │ active  │ 可发
            └────┬────┘
                 │ 不达标 + 确认后
                 ▼
         ┌────────────┐
         │  suspect   │ 疑似 (不阻止发, 仅标记)
         └─────┬──────┘
               │ 2 次不同组合 suspect 升级
               ▼
         ┌────────────┐
         │  frozen    │ 冻结 (X 轮内不发)
         └─────┬──────┘
               │ 冷却期满 (通道 20 轮/模板 10 轮/组合 5 轮)
               ▼
         ┌────────────┐
         │ probing    │ 试探 (放 1 轮验证)
         └──┬──────┬──┘
            │      │
    3 轮 0  │      │ 有 click/FTD
            ▼      ▼
     ┌───────────┐  ┌────────────┐
     │ permanent │  │   active   │ 复活
     │  (永冻)   │  └────────────┘
     └───────────┘
```

## 判定规则 (Q1=C: click + FTD 混合)

### ⚠️ 数据源规则 (2026-04-24 血泪)

**所有 click/reg/ftd 判定必须读 `stats.db.batches` 表 (replay-dashboard 口径)**, 不要用 visits API 或 `sessions.final_click_count` (那是老监测脚本的 visits 数据, 会低估点击数). 

实测: #67 在 visits 口径 click=5, 在 replay-dashboard click=75, **15 倍差距**, 如果拿 visits 判 suspect 会误冻爆款.

判定字段对照:
```sql
-- 正确口径:
SELECT seq, success_count AS sent, clicks, registrations AS reg, 
       ftd_count AS ftd, ai_roi, health_score
FROM batches WHERE seq=?
```

### 触发 suspect (告警但不阻止)

| 信号 | 条件 | severity | 数据源 |
|------|------|----------|--------|
| 零点击 | 1 轮 sent>=100 且 `batches.clicks`=0 | S1 (低) | batches |
| 低点击 | `batches.ctr` < 0.5% | S1 (低) | batches |
| 点击但无注册 | ctr >= 1% 但 `registrations` = 0 且 T+1 | S2 (中) | batches |
| 注册但无 FTD | `registrations` >= 3 但 `ftd_count` = 0 且 T+30 | S2 (中) | batches |
| 负 ROI | `sms_cost` > `net_pnl_amount` 且样本 >= 300 条 | S3 (高) | batches |

### 升级 frozen (实际阻止发)

| 来源 | 条件 |
|------|------|
| 跨 2 次不同 round 的 S1/S2 | 升级 frozen |
| 单次 S3 (负 ROI) | 直接 frozen |
| 通道级 | 该通道下 >= 3 个组合 frozen → 通道 frozen |
| 模板级 | 该模板下 >= 3 个组合 frozen → 模板 frozen |

### 升级 permanent (永冻)

| 条件 |
|------|
| probing 3 次全 0 click |
| frozen 90 天内解冻试探无一次达标 |
| 手动标记 (Willy "永冻 #N") |

### 冷却时间

```
组合级 frozen:  5 轮 (按 all rounds 计, 不是该组合 5 轮)
通道级 frozen:  20 轮  
模板级 frozen:  10 轮
permanent:     永远, 除非手动解
```

## 粒度 (Q2=d 三层都支持)

```
combo_coverage.is_frozen         (组合级)
pool.json channels[i].frozen     (通道级, 新增字段)
pool.json templates[i].frozen    (模板级, 新增字段)
policy.json.suspect_log[]        (观察历史)
policy.json.frozen_until_round[] (冷却期)
policy.json.permanent_black[]    (永冻池)
```

AI 判定时按"最严级别"取:
```
组合 #67 的真实可用性 = NOT (combo_frozen OR ch_frozen OR tpl_frozen)
```

## 半自动流程 (Q3=II)

### 触发点 1: 一 round 跑完

```
bowjwj-auto-campaign / bowjwj-batch-send 跑完后, AI 自动读:
  1. operations-report 该 round 的 clicks/registrations/ftd
  2. combo_coverage 历史累计
  3. 按判定规则算当前 severity
  4. 如果有状态变更建议 → 一条消息给 Willy:
  
"📋 round batch-xxx 完成, 我观察到:
  🟡 #68 触发 suspect_no_register (CTR 1% 但 0 注册, T+1)
  🔴 #120 连续 2 轮 S1, 建议 frozen (冷却 5 轮)
  ✅ #67 恢复 active (probing 有 1 click)

要我写入 policy 吗? (A=全接受 / G=逐个确认 / N=都不写)"

等 Willy 回复.
```

### 触发点 2: 手动命令

```
"冻 #67"                           → 确认 severity 后写 combo_frozen
"永冻 #120"                        → 直接写 permanent_black
"解冻 #N"                          → 从 frozen_until_round 移除
"冻 九 LuckyPlay 通道 20 轮"       → 写 ch_frozen
```

### 触发点 3: 巡检 "刷新冻结判定"

```
全扫 combo_coverage:
  1. 对每个 tested_rounds > 0 的组合
  2. 拉最新 operations-report 近 7 天
  3. 应用判定规则
  4. 产出 "变更清单", 给 Willy 批
  5. 批后一次性写 policy.json
```

## 数据结构 (policy.json 扩展)

```json
{
  "round_counter": 5,
  "suspect_log": [
    {
      "ts": "2026-04-24T01:30+08:00",
      "seq": 68,
      "severity": "S2",
      "reason": "no_register",
      "round_id": "batch-...-seq68",
      "metrics": {"ctr": 1.0, "registrations": 0, "ftd": 0}
    }
  ],
  "frozen_combos": {
    "67": {"since_round": 3, "until_round": 8, "reason": "2x_S1_zero_click"}
  },
  "frozen_channels": {
    "165b9ca3": {"since_round": 3, "until_round": 23, "reason": "3_combos_frozen"}
  },
  "frozen_templates": {},
  "permanent_black": {
    "combos": [],
    "channels": [],
    "templates": []
  },
  "probing": {
    "67": {"attempts": 0, "since_round": 8}
  }
}
```

## 查询视图 (Willy 问)

### "看冻结池"
```
🧊 冻结池状态 (round 5)
━━━━━━━━━━━━━━━━━━━━━━━━
活跃可发:      555 / 561  (98.9%)
Suspect 观察:  4 (S1=2, S2=2, S3=0)
冻结:          1 组合 · 0 通道 · 0 模板
  #67: 冻至 round 8 (还 3 轮, 原因: 2x_S1)
试探中:        0
永冻:          0

Top 3 suspect:
  #68 S2 (CTR 1% 但 0 注册, 观察至 T+7)
  #120 S1 (0 click, 1 次, 待下次确认)
  ...
```

### "看 suspect"

列出所有 suspect_log 最近 20 条, 按 severity desc.

### "#67 冻结状态"

```
#67 Smart 大官人加白 3 × 九 LuckyPlay S
  当前状态: frozen
  冷却至:   round 8 (还 3 轮)
  原因:     2x_S1 (cross-round zero_click)
  历史:
    round 3: S1 zero_click_30min
    round 4: S2 rejected_at_release (Willy 拒绝放量)
    → 升级 frozen
  通道层: 165b9ca3 (九) active (当前该通道 frozen 组合数 1 / 阈值 3)
  模板层: c9eb4bfe (加白 2) active
```

## 与其他 skill 的边界

```
bowjwj-auto-campaign / batch-send 跑完 verdict() 后:
  → 调 "刷新冻结判定" 流程 (本 skill)
  → 本 skill 输出建议, 等 Willy 批
  → 写入后 combo_coverage.is_frozen 更新
  → next round 发起时, batch-send 要 SKIP 掉 frozen 的 seq

bowjwj-batch-send 发起时:
  1. 解析 targets (seq_list)
  2. 过 frozen-manager 的"当前冻结池" filter
  3. 被过滤的 seq 在清单里标红 "SKIPPED (frozen)"
  4. Willy 可 override: "强制发 #67 (含冻结)"
```

## ⚠️ 已知坑

1. **samples 不够不判**: sent < 100 不判 S1/S2 (样本太小, 噪声), 只记观察
2. **FTD 滞后**: 新 round 跑完 T+0 就判 "no_ftd" 会冤枉, 至少等 T+1 (S2) / T+30 (S3 negative ROI)
3. **probing 必须独立 round**: 冷却期满试探那 1 轮要纯净, 别混在批量里
4. **模板/通道升级阈值**: 3 个组合 frozen 才升级, 避免单点故障误伤整行
5. **解冻后前 3 轮观察**: probing 状态严格 1 轮, 过了就回 active 或进 permanent
6. **Willy 拒绝放量 ≠ 自动 suspect**: 可能 Willy 有外部判断 (如当前不在窗口), 别误判.
7. **Willy 拒绝放量 ≠ 自动 suspect**: 可能 Willy 有外部判断 (如当前不在窗口), 别误判
8. **operations-report 60s 缓存**: 刚跑完的 round 立刻判, 数据可能滞后, AI 要明示
9. **permanent 不可逆** (除非手动删), AI 提议 permanent 必须显眼警告
10. **"每 batch 1 reg" 系统伪信号** (2026-04-24 实测): 新建 agent_line 默认带 1 个系统账户, 不是真用户. **判业绩必须 reg >= 2 才算真信号**, ftd >= 1 才是金标准.
11. **判决时间窗口别太早**: click T+30min 基本稳定, 但 reg 要 T+2h, ftd 要 T+24h. L3 判决 check_after_min 应 >= 120min, 而不是 35min.
12. **效果差别急着冻**: 先查 3 件事 — 短链域名可用性 (curl -I), send-log 投递数, 料子质量对比. 2026-04-24 seq68-release 18/19 组合 0 click, 差点冤枉冻了, 真因是 now.vip 域名挂了.

## 红线 (不做的事)

- ❌ 不写自动 cron (判定按 Willy 触发, 他说 "刷新冻结" 才跑)
- ❌ 不自动升级到 permanent (永冻必须 Willy 明确确认)
- ❌ 不跨账号 (只管自己的)
- ❌ 不跨 backend (只 NN33 ph)
- ❌ 不自作主张 override Willy 的 "强制发"
- ❌ 不自带脚本 (纯协调)

## 依赖 skills

```
bowjwj-auto-campaign     — round verdict 触发本 skill 刷新
bowjwj-batch-send        — 发起前 consult 本 skill 过滤
bowjwj-conversion-funnel — 读 FTD/ROI 信号 (S3 判定必需)
bowjwj-send-analysis     — 读 CTR/register 信号 (S1/S2 判定必需)
```
