---
name: bowjwj-seq-orchestrator
description: bowjwj seq 智能调度协调器。Willy 说"今天跑啥"、"推荐 seq"、"自动挑任务"、"接下来发什么"、"排今日计划"时加载。综合 561 组合覆盖率 + 库存 + 时间窗口 + TG 可用性 + 冻结池 + 历史 ROI, 推荐今日最优跑哪几个 seq。纯策略协调, 不自动发。
---

# bowjwj-seq-orchestrator (协调器)

## 何时触发

**规划**:
- "今天跑啥" / "接下来发什么"
- "推荐 seq" / "自动挑任务"
- "排今日计划"

**场景式**:
- "我有 30 分钟, 跑啥"
- "预算 $10, 怎么分"
- "还剩库存 Smart 100K, 跑啥组合"

**晨报模块**:
- 被 daily-playbook 调拿"今日 3 件事"

## 协调目标

**纯策略层**, 不发信. 综合 6 个维度打分, 输出"按优先级排序的 seq 清单". Willy 决定跑不跑, 怎么跑.

## 决策因子

| 因子 | 数据源 | 权重 |
|------|--------|------|
| 覆盖率 (未测优先) | combo_coverage.tested_rounds=0 | 30% |
| 历史 ROI (已测高 ROI 放量) | combo_coverage 或 operations-report | 25% |
| 库存可用 (运营商匹配) | pack-health-monitor | 15% |
| 通道健康 (绿通道优先) | channel-health | 10% |
| 冻结状态 (frozen 跳过) | frozen-manager | 必过 (硬筛) |
| 时间窗口 (当前 BJ 时段可发) | 本地判断 | 必过 (硬筛) |
| TG 可用性 (Willy 在线否) | 手动配置 | 软 |
| 模板衰减 (衰减模板降权) | template-evolution | 10% |
| 组合多样性 (别all 一模板) | 本 skill 自算 | 10% |

## 3 种调度模式

### 模式 A: Explore (探索新组合)

```
目标: 提升覆盖率
选 seq:
  tested_rounds = 0 AND NOT frozen
  按 (通道健康 × 模板预期 × 库存) 打分
  Top 5-10 推荐

举例:
  "今天跑 5 个未测 Smart 侧组合:
   #2 (大官人加白3 × 三yo家 VKRealm)
   #4 (大官人加白3 × 六yo家 VKQuest)
   ..."
```

### 模式 B: Exploit (放量已知高 ROI)

```
目标: 赚钱
选 seq:
  tested_rounds >= 2 AND ROI > 1 AND ftdRate > 2%
  按 (ROI × 库存) 排序
  Top 3-5

举例:
  "今天放量 3 个: #67 (ROI 1.8), #XX, #XX
   预算 ~$25, 预期利润 ~$45"
```

### 模式 C: Mixed (60% 探索 + 40% 放量) ← 推荐默认

```
1/3 时段跑探索, 2/3 时段跑放量
或: 同批并发探索 60% + 放量 40%
平衡短期收入 + 长期覆盖
```

## 时间窗口硬约束

```
发送窗口 (BJ 时区 NN33 ph 经验):
  12:00 - 02:00 (14 小时)
  
窗口外创 campaign 系统不强制拒, 但:
  发送效果差 (对方睡觉时间)
  CTR 衰减 50%+
  
推荐: 按当前 BJ 时间决定
  in window:         直接跑
  窗口外 1h 内:      规划 plannedAt 到窗口开
  窗口外 >1h:       "等 12:00 再跑" + 生成计划
```

## TG 可用性逻辑

```
Willy 默认在线时段: BJ 10:00 - 02:00
不在线时段 (03:00 - 09:00): 批量 > 5 必告警
Willy 可手动设 "TG 休假 X 小时" → silence batch scheduling
```

## 推荐输出格式

```
🎯 今日 seq 调度建议 (09:00 BJ)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

模式: Mixed (60% 探索 + 40% 放量)
当前库存: Smart 3.25M, Globe 490K, DITO 310K
窗口: 12:00 - 02:00 BJ, 还 3h 开

📅 12:00-14:00 放量 batch (3 个):
  #67 大官人加白3 × 九 LuckyPlay  ROI 1.8 → 20 pack
  #XX ...                              
  #XX ...
  预算 ~$25  TG 批准 3 次

📅 14:00-16:00 探索 batch (5 个新组合):
  #2 #4 #6 #8 #10  (Smart 侧 yo家通道轮巡)
  预算 ~$1.4  TG 批准 5 次

📅 16:00-18:00 Globe 侧探索 5 个:
  #250 #252 ...
  预算 ~$1.4  TG 5 次

今日总预算: ~$28
今日总 TG: 13 次
预期覆盖率提升: 2.1% (+13 组合)
预期利润: ~$40 (从放量 batch)

要跑吗? (A=按此计划 / M=手动调整 / N=取消)
```

## 与其他 skill 边界

```
读方:
  pool.json                561 组合定义
  combo_coverage           已测覆盖率
  operations-report        历史 ROI
  pack-health-monitor      库存
  channel-health           通道黑名单
  frozen-manager           冻结池
  template-evolution       衰减模板降权

写方:
  不直接发, 只生成计划
  Willy A → 调 batch-send 执行
  Willy M → AI 协助修改
```

## 打分公式 (未来可调)

```
score(seq) = 
    30 * normalize(1 - coverage)              # 未测加分
  + 25 * normalize(historical_roi)           # 历史 ROI
  + 15 * normalize(pack_inventory_for_carrier) 
  + 10 * channel_health_score
  - inf  * frozen_penalty                    # 冻结立即 0
  - inf  * out_of_window_penalty            # 窗口外立即 0
  + 10 * (1 - template_decay)
  + 10 * diversity_bonus                    # 不重复同 tpl

按分排序 Top N
```

## 已知坑

1. **新组合首次无 ROI**: 模式 B 时候没历史, 按通道 + 模板单独打分代偿
2. **库存挑完之后**: 如果某运营商池被本轮选光, 下一轮要重拉更新
3. **TG 可用性判断**: 没法真判, 只能 Willy 配
4. **推荐 vs 自动执行**: 本 skill 永远推荐 + 等 A/G, 不自动
5. **多样性**: 50 个 seq 不能都同 tpl, 加强制分散
6. **时段迁移**: 过了 14:00 后推荐要重算
7. **预算超**: 推荐总预算必须 <= 已配 daily budget
8. **预期利润不准**: 探索 batch 预期按基线平均, 不对实际预测

## 红线

- 不自动发 (只推荐)
- 不自动冻 (不吞 frozen-manager 的活)
- 不修改 policy.json
- 不跨 backend
- 不算超 30 天预算

## 依赖 skills

```
pool.json / combo_coverage  通过 batch-send 或直接读
bowjwj-conversion-funnel    历史 ROI
bowjwj-pack-health-monitor   库存
bowjwj-channel-health       通道健康
bowjwj-frozen-manager       冻结池
bowjwj-template-evolution   衰减模板
bowjwj-batch-send           执行方
bowjwj-daily-playbook       消费方 (晨报 3 件事)
```
