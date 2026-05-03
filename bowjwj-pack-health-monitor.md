---
name: bowjwj-pack-health-monitor
description: bowjwj 号码包库存健康监控协调器。Willy 说"看库存"、"包健康"、"号码还剩多少"、"采购预警"、"Smart 包够用吗"、"老化包识别"、"reuseLocked 池"时加载。phone-packs API 实时拉, 按运营商/来源/年龄/锁定状态多维度盘点, 产出采购预警。薄协调器。
---

# bowjwj-pack-health-monitor (协调器)

## 何时触发

**总览**:
- "看库存" / "包健康"
- "号码还剩多少"
- "今日库存巡检"

**维度**:
- "Smart 包够用吗"
- "Globe 包占比"
- "老化包" / "X 天前上传的还没用"

**锁定/预留**:
- "reuseLocked 池" (被手动锁, 不可重复用)
- "assignmentCampaignId 的那些"

**预警**:
- "采购预警"
- "该买什么运营商的了"

## 协调目标

薄协调, 实时拉 `/api/phone-packs` + 本地统计. 不落库. 阈值 + 判定硬编码.

## 数据源

### 单刀: `/api/phone-packs`

```
GET /api/phone-packs?pageSize=500&page=N&backendInstanceId=<BID>
返回 data[]:
  id / source / cleanCount / totalCount
  backendInstanceId / countryCode
  packIndex / totalPacks / totalRowsInFile
  assignmentCampaignId     非 null = 已被绑定到 campaign
  reuseLocked              true = 手动锁定, 不能复用
  reuseUnlockedAt
  createdAt                上传时间, 用于老化
  uploadedByUserId
```

翻页到底 (NN33 ph ≈42K 包, 85 页). 单次巡检 ~90s.

## 维度分类 (总览)

```
按状态:
  可用 (available)   cleanCount>0 && assignmentCampaignId=null && !reuseLocked
  已用 (used)        assignmentCampaignId != null
  锁定 (locked)      reuseLocked=true
  空 (empty)         cleanCount=0

按来源 (source 前缀 + skill):
  正常              source 不含 "黑名单"
  yo家黑名单         source 含 "yo家黑名单"   ← skill 已过滤

按运营商 (解析 source):
  Smart / TNT       "Smart" 或 "TNT" 关键词
  Globe / DITO      "Globe" 或 "DITO" 关键词  
  未标记            其他

按年龄:
  新 (<= 3 天)       createdAt 距今 <= 3 天
  中 (3-14 天)
  老 (> 14 天)       老化中, 建议优先用

按来源 Top 10:
  source key · pack_count · total_number · 可用 vs 已用
```

## 视图组装

### 1) 总览 "看库存"

```
📦 NN33 ph 号码库存 (拉了 85 页)

总览:
  全部包数:    42,484
  可用:        42,113 (99.1%)   总 4.22M 号
  已用:             0 (0%)      后台字段未维护 (看 combo_coverage 反推)
  锁定:             0
  黑名单(跳过): 347 (29K 号)

按运营商 (可用):
  Smart + TNT:  33,291 包  3.25M 号
  Globe:         5,273 包  490K 号
  DITO:          2,457 包  310K 号
  未标记:           22 包  21K 号

按年龄:
  <= 3 天:    N 包   X 号
  3-14 天:   N 包   X 号
  > 14 天:   N 包   X 号  ⚠️ 建议优先用

Top 10 来源: (同 dashboard inventory)
```

### 2) "Smart 包够用吗"

```
Smart 可用: 33,291 包 · 3.25M 号
预估消耗速度: 
  按最近 7d operations-report sum(sentCount) WHERE 通道=Smart
  假设 = 500K/周 → Smart 可撑 ~46 周
  
判定:
  > 4 周库存 → ✅ 充足
  2-4 周     → 🟡 2 周内补
  < 2 周     → 🔴 立即补
```

### 3) "老化包识别"

```
SELECT from phone-packs WHERE createdAt < today - 14 days
  AND assignmentCampaignId IS NULL  
  AND !reuseLocked
按 createdAt 升序 (最老的优先)
输出: pack_id 缩写 · source · cleanCount · 上传日期 · "建议优先跑"
```

### 4) "reuseLocked 池"

```
GET /api/phone-packs?pageSize=500  过滤 reuseLocked=true
列清单: pack_id · source · 锁定原因 (后台没字段, 可能 remark)
提供 "bulk-unlock" API 但不自动调, 提示 Willy 手动
```

## 采购预警逻辑

对每运营商组:
```
需求 = 未来 30 天预估消耗 (按近 7d × 4 或 seasonal factor)
库存 = 当前 available_numbers
安全线 = 需求 × 1.5

库存 < 需求         → 🔴 紧急采购
库存 < 安全线       → 🟡 本周采购
库存 >= 安全线      → ✅ 足够
```

如果 Smart + Globe 都红, 触发 "全线补库" 告警.

## 与其他 skill 边界

```
bowjwj-data-sourcing (s9):
  兄弟 skill. 关注"这批料买得值不值"
  本 skill 关注 "库存还剩多少天"
  
  数据互通: source_quality 里的 ROI + 本 skill 的库存 =
    "优质料子还剩 N 天" vs "亏本料子还剩 M 天"

bowjwj-batch-send:
  发起前 consult 本 skill 找可用 pack
  ★ 本 skill 提供 pick_pack(carrier, count) 规则
  
bowjwj-alert-manager (s13):
  消费本 skill 的 🔴 采购告警
```

## pick_pack 规则 (供 batch-send 调)

```
pick_pack(carrier="Smart", need_count=20) 返回策略:
  1. WHERE carrier_group=Smart AND available AND not_blacklist
  2. ORDER BY 
     (a) 质量分 (data-sourcing source_quality.quality_score DESC)
     (b) createdAt ASC (老化优先)
     (c) packIndex ASC
  3. LIMIT N
```

## 已知坑

1. **后台 assignmentCampaignId 几乎不维护**: 大多为 null, 即使这包已发过. 要结合 stats.db.sessions 反查 pack_ids_json 才能真正知道"用过没"
2. **42K 包翻 85 页耗时 ~90s**: 加 cache, TTL 10 分钟
3. **运营商标记 source 不一定全**: "willy哥专用 - Smart" 有标, "0418银河数据 30 1包" 没标 (靠 -Smart 后缀才认)
4. **cleanCount 0 的包很多**: 过滤掉后才是真可用
5. **老化时间阈值 14 天**: 经验值, 没科学依据, Willy 可调
6. **采购预估**: 按过去 7 天外推 30 天线性, 有促销期可能不准
7. **未标记 22 包**: 手动处理或跳过
8. **翻页可能重复**: 后台如果有新包创建, 翻页位移, 总 count 先记下作 anchor

## 缓存策略

```
单次巡检结果落 ~/.hermes/state/bowjwj/inventory-snapshot.json
TTL 10 分钟, 老于则重拉
AI 触发时先查 snapshot.generated_at, 够新直接读
```

## 红线

- 不 bulk-delete 包
- 不 bulk-unlock (reuseLocked 要 Willy 手动)
- 不自动采购 (只告警, 决策 Willy)
- 不猜运营商 (无法从 source 识别就标"未标记")
- 不跨 backend

## 依赖 skills

```
bowjwj-aicrm             API 地图 (phone-packs)
bowjwj-data-sourcing     共用 source_quality 数据
bowjwj-batch-send        provide pick_pack 规则
bowjwj-alert-manager     消费采购告警
```
