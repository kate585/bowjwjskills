---
name: bowjwj-intervention
description: bowjwj 自动介入停止。Willy 说"冻 #N"、"解冻 #N"、"看冻结池"、"告警"、"有啥异常"、"跟单 #N"、"看跟单队列"、"确认 A #N"、"停发信"时加载。冻结/告警/跟单三合一，自动异常检测 + 半自动确认执行。
---

# bowjwj-intervention (自动介入停止)

## 三大子系统

### 1. 冻结管理 — 组合/通道/模板三级冻结
### 2. 告警管理 — 红黄告警聚合 + TG 投递
### 3. 跟单控制 — 指数递增放量，每层自动判决

---

## 一、冻结管理

### 何时触发

- "冻 #67" / "永冻 #120" / "解冻 #N"
- "看冻结池" / "哪些组合该冻" / "刷新冻结判定"
- "冻 九 LuckyPlay 通道" / "冻 G1 模板"

### 三级冻结

| 级别 | 粒度 | 判据 | 冷却 | 操作 |
|------|------|------|------|------|
| suspect | combo | sent >= 500, click = 0 | - | 自动标记 |
| frozen | combo | suspect 持续 3 轮 OR click = 0 & sent >= 1000 | 7 天 | AI 提议→Willy A |
| permanent | combo/channel/template | frozen 3 次仍 0 click OR 通道连续挂 | ∞ | Willy 确认 |
| channel_frozen | channel | configInvalidSince 非空 OR 失败率 >30% | 手动 | AI 提议→Willy A |
| template_frozen | template | 连续 5 个 combo 零点击 OR spam_score < 0 | 手动 | AI 提议→Willy A |

### 本地状态

```
policy.json → 冻结名单
stats.db.combo_coverage → is_frozen, frozen_at, freeze_reason
```

### 解冻规则

```
frozen + 冷却期满 + 库存充足 → 建议解冻 1 包试水
permanent → 永不解冻 (除非 Willy 手动)
```

---

## 二、告警管理

### 何时触发

- "看告警" / "有啥异常" / "告警历史"

### 告警级别

```
🔴 红 (TG 通知):
  - 通道挂 (configInvalidSince 非空)
  - JWT 7 天过期
  - 连续 5 轮 zero_click
  - 负 ROI 持续 24h
  - 域名活性检测失败 (now.vip 等)
  - 采购预警红 (库存 < 24h 用量)

🟡 黄 (events.jsonl):
  - 单轮 zero_click
  - CTR < 中位数 50%
  - 模板衰减 (CTR 7 天降 >30%)
  - 号码包老化 (>14 天)
  - balance < 5000 条
```

### 去重规则

- 同类型告警 30 分钟内不重复投递
- 红告警 TG 投递后有 2h 冷却
- 手动标记 "已处理" 后不再提醒

### 处理命令

```
"标记 #ALERT-X 已处理"
"忽略这个告警"
"静默 XX 小时"
```

---

## 三、跟单控制

### 何时触发

- "跟单 #N" / "启动跟单 #N L0"
- "看跟单队列" / "跟单状态"
- "确认 A #N" / "不跟 #N" / "暂停 #N"

### 4 层指数递增 (1→5→10→20 包)

| 层 | 包数 | 号码量 | 判决条件 | 自动? | 等待窗口 |
|----|------|--------|---------|-------|---------|
| L0 | 1 | 50-100 | click >= 3 | ⚙️ 自动→L1 | T+20min |
| L1 | 5 | 250-500 | click >= 10 或 CTR >= 2% | 🟡 建议→L2, Willy A | T+20min |
| L2 | 10 | 500-1000 | click >= 20 或 reg >= 2 | 🟡 建议→L3, Willy A | T+30min |
| L3 | 20 | 1000-2000 | ftd >= 1 或 reg >= 5 | 🟡 建议→L4, Willy A | T+60min |

### 自动停止条件

```
L0 停止: click = 0 & polled >= 30min → 标记 suspect
L1 停止: click < 5 & polled >= 60min → 回退 L0 观察
L2 停止: reg < 2 & polled >= 90min → 标记 frozen
L3 停止: ftd = 0 & polled >= 120min → 不建议继续放量
全局停止: 连续 5 轮 zero_click → 暂停发信，等 Willy 决策
```

## 自动停止触发条件

```
触发 "暂停发信":
  - 连续 5 轮 zero_click (所有 session 零点击)
  - 通道全域失败 (3+ 通道 configInvalidSince 非空)
  - 域名全挂 (所有 active 域名活性检测失败)
  - JWT 过期 (401 响应)
  - IP 被 ban (403 IP_NOT_WHITELISTED)

恢复:
  - Willy 说 "继续发信" 或 "解冻 XX"
  - 冷却期满 + AI 建议恢复
```

## 禁区

- ❌ 永冻操作需 Willy 二次确认
- ❌ 通道冻结不可逆 (除非 Willy 手动)
- ✅ 自由: 查询冻结池、告警历史、跟单状态
