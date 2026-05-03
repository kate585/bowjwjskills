---
name: bowjwj-daily-playbook
description: bowjwj 日常 playbook 协调器。Willy 说"早安"、"日巡检"、"今天干啥"、"晨报"、"今天 3 件事"、"今日复盘"时加载。组合 channel-health + pack-health + frozen-manager + conversion-funnel 出 1 份 "今天 3 件事" + 昨日复盘 + 本周走势。可接 cron 早 9 点自动跑。薄协调。
---

# bowjwj-daily-playbook (协调器)

## 何时触发

**晨间**:
- "早安" / "晨报" / "早 9 点了"
- "今天干啥" / "今天 3 件事"

**晚间**:
- "今日复盘" / "今天赚了多少"
- "明天 priority"

**周/月**:
- "本周复盘" / "本月复盘"
- "周报"

**主动** (cron):
- 每天 BJ 09:00 自动跑一次, 发 TG

## 协调目标

薄协调器, 调其他 skill 聚合. 输出格式化晨报. 不落库, 不决策, 只汇总 + 建议.

## 晨报模板 (固定格式)

```
☀️ bowjwj 晨报 · 2026-04-24 (周四) 09:00 BJ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 昨日业绩 (operations-report groupBy=date)
  发送:  XXX,XXX (Smart X% / Globe X% / DITO X%)
  点击:  XXX (CTR X.X%)
  注册:  XX
  FTD:   X (注册→FTD X.X%)
  存款:  ₱X,XXX
  成本:  ₱X,XXX (SMS)
  利润:  ₱X,XXX (ROI X.X)

📈 本周累计 (近 7 天):
  sent XXM · click XXk (CTR X%) · FTD XX · 利润 ₱XX,XXX · ROI X.X

🎯 今天 3 件事 (按 priority):
  1. 🔴 [紧急] XX 通道 failed 率 >20%, 建议暂停
     (channel-health 扫出 / frozen-manager 建议冻结)
  2. 🟡 [本周] Smart 包库存 < 2 周, 安排采购
     (pack-health 采购预警)
  3. 🟢 [迭代] 模板 "小陈 43" 全系统 Top 1 CTR 14%, 学结构
     (template-evolution 推荐)

📋 冻结池变动:
  新增 suspect: #68 (CTR 1.0% 但 0 注册)
  待解冻: 无

🧊 JWT 续期: 7 天后过期 (2026-05-01)

📱 TG 待办:
  今日未批准 approval: 0 条
  昨日批准: N 次 (平均响应 M 分钟)

💡 建议:
  上午 9-12 跑什么 (seq-orchestrator 提供)
  下午 14-18 跑什么
```

## 视图组装流程

```
1. conversion-funnel 拉昨日 + 7d summary (groupBy=date)
2. pack-health 扫库存 + 采购预警
3. channel-health 扫全通道健康, 取红黄告警
4. frozen-manager 读 policy.json 取 suspect/frozen 变动
5. template-evolution 拿 Top 模板 (intelligence textCopy Top 3)
6. seq-orchestrator 提供今日推荐任务 (可选)
7. AI 按模板格式化输出
```

## 3 件事优先级规则

```
🔴 紧急 (必须今天做):
  - 通道 failed 率 >20% (channel-health 红)
  - 冻结池积压 (frozen-manager suspect >= 5)
  - 负 ROI campaign 还在跑
  
🟡 本周 (这周要做):
  - 采购预警 (pack-health 黄或红)
  - 模板衰减 (template-evolution 衰减 >30%)
  - JWT 7 天内过期
  
🟢 长期 (可做可不做):
  - 学习标杆 (template-evolution Top 文案分析)
  - 新组合测试 (seq-orchestrator 推荐未测 seq)
  - A/B 对比实验
```

## 晚报格式 (简版)

```
🌙 bowjwj 晚报 · 2026-04-24 22:00

今日完成:
  批次 N · 发送 XXX · 点击 X · 注册 X · FTD X · 利润 ₱XX

明日 priority (AI 重算):
  1. XX
  2. XX
  3. XX

入睡建议: 
  凌晨无窗口, 下批跑 12:00 BJ
```

## 周报 / 月报模板

```
周一早 9 点自动补一份上周周报:
  本周 vs 上周 对比 (sent/FTD/ROI 环比)
  Top 3 爆款组合 (seq)
  Bottom 3 冻结组合
  供应商 ROI 排行 (data-sourcing)
  采购 vs 产出 (本周花了 $X 买料, 跑出 $Y 收入)
```

## 与 cron 集成

```
建议 cron:
  BJ 09:00 daily   → "早安" 触发晨报, deliver TG
  BJ 22:00 daily   → "晚报" 触发, deliver TG  
  BJ 09:00 Mon     → 周报附加
  BJ 09:00 每月 1  → 月报附加

cron 创建时选 local 模式先手动验证, OK 再接 TG
```

## 与其他 skill 边界

```
本 skill = 聚合展示层, 不做任何决策
所有数据 / 判定都来自:
  conversion-funnel  (业绩)
  channel-health    (通道告警)
  pack-health       (库存告警)
  frozen-manager   (冻结状态)
  template-evolution (模板建议)
  seq-orchestrator  (今日推荐任务)
```

## 已知坑

1. **cron 跑时没 context**: 早 9 点 AI 不知道"Willy 昨晚做了啥", 靠 stats.db + 线上数据都够
2. **TG 投递格式**: TG markdown 限制, 别用 emoji 塞满, 降级纯文本
3. **晨报数据滞后**: operations-report 有 60s cache, 昨日数据 T+0 9 点可能昨晚的 campaign 还没 snapshot
4. **cron 幂等**: 同一天多次调不重复发, 加个 "已送" 标记
5. **JWT 过期 cron 先检查**: 过期 skill 什么都拉不到
6. **周一要上周周报**: 日报逻辑 + 额外周报块, 别拆 2 skill

## 红线

- 不写 cron 本身 (本 skill 是"工作内容", cron 由 Willy 决定开不开)
- 不自动改配置
- 不自动放量
- 不发 alert 到 TG (那是 alert-manager 的活)
- 纯聚合, 决策 Willy

## 依赖 skills

```
bowjwj-conversion-funnel  数据主力
bowjwj-channel-health     告警源
bowjwj-pack-health-monitor 库存源
bowjwj-frozen-manager     冻结源
bowjwj-template-evolution 建议源
bowjwj-seq-orchestrator   任务源 (可选)
bowjwj-alert-manager      互不干扰
```
