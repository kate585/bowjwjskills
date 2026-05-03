---
name: bowjwj-copy-test
description: bowjwj 文案测试流水线。Willy 说"测文案"、"跑文案测试"、"开始测话术"、"看测试进度"、"测试结果"、"文案通过库"、"效果文案库"时加载。每天 100 条话术 × 2000 条/条 = 20 万条测试量，多通道并发降低代理线占用，自动筛选 CTR>=5% 入库。
---

# bowjwj-copy-test (文案测试流水线)

## 🔴 三条铁律 (2026-04-29)

### 1. 票卷: RAFFLE 2659055 + 7D, POST 创建时设, PATCH 不生效
### 2. 通道匹配: Smart→Smart通道, Globe→Globe通道, GG全网通=双通
### 3. 代理线: 1tpl × 1ch × Npack = 1 agent_line, 多文案=多代理线

## 核心设计

```
每日流程:
  1. copy-generate 生成 100 条话术 (Globe 50 + Smart 50)
  2. 每条话术测 2000 条 (8 通道并发 × 1 包/通道 × 100 条 = 800 条/轮)
  3. T+30min 读 replay-dashboard 拿 PH IP CTR
  4. CTR >= 5% → 入库「效果文案库」供自动发信调用
  5. CTR >= 2% → 入库「测试通过库」备选
  6. CTR < 2% → 标记淘汰
```

## 降低代理线占用策略

```
旧方式 (1通道1包):
  每条话术: 1 通道 × 20 包 = 20 个 agent_line
  100 条话术 = 2000 个 agent_line  ← 爆炸

新方式 (8通道并发, 1包):
  每条话术: 8 通道 × 1 包 = 1 个 session = 1 个 agent_line
  100 条话术 = 100 个 agent_line  ← 降低 20 倍

原理:
  POST /send-direct/test-send
    templateIds: [1个话术]
    smsInstanceIds: [8个通道]  ← 8 通道同时发
    phonePackIds: [1个包]      ← 只 1 包 = 1 session
  → 1 个 agent_line 覆盖 8 通道的测试数据
  → 1 包 100 条 × 8 通道 = 800 条同时发出
  → 测 2000 条只需 3 轮 (800+800+400)
```

## 何时触发

**启动**:
- "测文案" / "跑文案测试" / "开始测话术"
- "今天测 100 条文案" / "开始每日文案测试"

**进度**:
- "看测试进度" / "测了多少了" / "还有多少没测"

**结果**:
- "测试结果" / "今天哪些话术过了"
- "看测试通过库" / "看效果文案库"

**入库管理**:
- "效果文案库里有多少条" / "清理过期文案"

## 每日测试节奏

```
BJ 时间线:
  00:00-07:00  休息 (不测试)
  07:00        自动启动: 生成 100 条话术 → 排队
  07:00-20:00  执行测试 (每 3 秒一轮, 8 通道并发)
  20:00-21:00  汇总结果, 排名, 入库
  21:00        输出测试日报

每轮节奏 (3 秒):
  - 本轮: 1 话术 × 8 通道 × 1 包 (800 条)
  - 每条话术: 3 轮 (800+800+400 = 2000 条)
  - 每 3 秒 = 测完 1 条话术的 1/3

全天产能:
  - 3 秒/轮, 13h 发送窗口 (07-20)
  - 理论 = 13×3600/3 = 15600 轮
  - 实际: 100 条 × 3 轮 = 300 轮/天 (足够)
  
通道分配:
  Globe 话术: 用 Globe 通道池 (9 条, 选前 8)
  Smart 话术: 用 Smart 通道池 (7 条 + GG家全网通 = 8)
```

## 测试执行流程

### Step 1: 话术生成 (copy-generate 产出)

```
输入: 运营商 (globe/smart), 方向 (6 方向轮换), 数量 = 50
输出: 50 个模板 ID 列表

每个模板确保:
  ✅ 过 5 条硬规则 + 红线检查
  ✅ spam_score >= 60
  ✅ Taglish 混搭, 含病词
  ✅ 已创建到 bowjwj (POST /api/campaign-templates)
```

### Step 2: 号码包准备

```
每轮消耗 1 包 (100 条) × 8 通道 = 800 条
每条话术需要 3 轮 = 3 包 (300 包号码)
100 条话术 = 300 包/天

包选择:
  Globe 话术 → Globe/Dito 包 (从银河数据0427 优先)
  Smart 话术 → Smart/TNT 包
  排除:
    ❌ 文件名/来源含「测试」→ 机器人不发
    ❌ 文件名/来源含「黑名单」→ 机器人不发
    ❌ 黑名单包 (phone-blacklists)

⚠️ 关键: 每话术每轮只选 1 个包 (降低 agent_line)
  不是 20 包, 是 1 包 × 8 通道
```

### Step 3: 发送 (test-send)

```python
# 每条话术的测试发送
POST /api/campaign-templates/{templateId}/send-direct/test-send
body = {
    templateIds: [templateId],           # 1 个话术
    smsInstanceIds: [ch1, ch2, ..., ch8], # 8 个通道
    phonePackIds: [packId],              # ★ 只 1 包
    shortlinkMappingMode: "recipient",   # 6 位号码级短链
    shortlinkMode: "domain",
    customShortlinkDomainConfigIds: [前 10 活跃域名],
    titlePrefix: "CPYTEST-YYYYMMDD-HHMM"
}
→ 返回 1 个 session (1 个 agent_line)
→ 系统自动发 1 包 × 8 通道 = 800 条
→ TG 审批 (走 tg_auto_approve.py 自动批)
```

### Step 4: 点击监控

```
等待 T+3min: 首次轮询
轮询: GET /api/send-verification-sessions?ids={sessionId}
判据: session.clickCount > 0 → passed

T+10min: 第 2 轮
T+30min: 最终判定

数据源切换 (T+30min):
  不再看 session.clickCount
  改看 replay-dashboard 的 headline.traffic.clicks (PH IP 过滤后)
```

### Step 5: 判定入库

```
CTR >= 5% (优质): ★ 效果文案库
  → 记录到 stats.db.effective_copies
  → 供 auto-campaign 优先调用
  → 标记方向、CTR、通道、时间

CTR >= 2% (通过): 测试通过库
  → 记录到 stats.db.tested_copies
  → 备选池，供 copy-generate 参考
  → 同方向生成变体继续测

CTR < 2% (淘汰):
  → 记录到 stats.db.rejected_copies
  → 标记原因 (低 CTR / 零点击)
  → 该方向降低生成优先级

CTR = 0% (零点击):
  → 直接淘汰
  → 检查是否触红 (有赌博关键词漏网?)
  → 该模板冻结
```

## 本地数据库

### 新建: stats.db.copy_test 表

```sql
CREATE TABLE copy_test (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id TEXT NOT NULL,
  template_name TEXT,
  carrier TEXT NOT NULL,            -- 'globe' or 'smart'
  direction TEXT NOT NULL,          -- '到账+限时' etc
  sms_text TEXT NOT NULL,
  spam_score INTEGER,
  channels_json TEXT,               -- 用哪 8 个通道
  pack_id TEXT,
  session_id TEXT,
  test_round INTEGER DEFAULT 1,     -- 1-3
  sent_count INTEGER,
  click_count INTEGER,              -- PH IP only
  ctr REAL,
  status TEXT DEFAULT 'testing',   -- testing/passed/rejected
  created_at TEXT,
  evaluated_at TEXT
);

CREATE TABLE effective_copies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id TEXT NOT NULL UNIQUE,
  carrier TEXT NOT NULL,
  direction TEXT NOT NULL,
  sms_text TEXT NOT NULL,
  best_ctr REAL,
  best_channel_id TEXT,
  tested_sends INTEGER,
  promoted_at TEXT,
  used_by_auto_send INTEGER DEFAULT 0,
  last_used_at TEXT
);

CREATE TABLE tested_copies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id TEXT NOT NULL UNIQUE,
  carrier TEXT NOT NULL,
  direction TEXT NOT NULL,
  sms_text TEXT NOT NULL,
  max_ctr REAL,
  status TEXT DEFAULT 'standby',
  created_at TEXT
);
```

## 效果文案库

### 入库标准 (CTR >= 5%)

```
筛选: PH IP clicks / sent >= 5%
条件: sent >= 500 (量级足够)
时效: 入库 7 天内有效, 过期重新验证
容量: 每运营商最多保留 20 条
排序: 按 CTR 降序
```

### 效果文案库文件

```
/c/Users/jack8/Desktop/bowjwj 发送模式更新脚本文件夹2/effective_copies.json
/c/Users/jack8/Desktop/bowjwj 发送模式更新脚本文件夹2/tested_copies.json
```

### 自动发信调用优先级

```
auto-campaign 选模板:
  1. 效果文案库里选最高 CTR 的 (效果已验证)
  2. 效果文案库空了 → 测试通过库里选最高的
  3. 都没了 → 触发 copy-generate 生成新话术
  4. 同一话术连续使用 10000 条 → 换同方向下一个
```

## 测试日报格式

```
🧪 文案测试日报 | 2026-04-28
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 测试: 100 条 (Globe 50 / Smart 50)
📨 发送: 200,000 条 (100 × 2000)
⏱️  耗时: X 小时
🔗 代理线: 100 个 (8通道并发, 降低 20 倍)

⭐ 效果文案库新增 (CTR >= 5%): X 条
✅ 测试通过 (CTR >= 2%): X 条
❌ 淘汰 (CTR < 2%): X 条
💀 零点击: X 条

🏆 Globe Top 3:
  1. [话术] | CTR=X% | 方向=到账+限时
  2. ...
  3. ...

🏆 Smart Top 3:
  1. [话术] | CTR=X% | 方向=对话式
  2. ...
  3. ...

📦 效果文案库: X 条可用 (Globe X / Smart X)
📦 测试通过库: X 条备选

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 建议: [基于今日测试的学习]
```

## 脚本 (待创建)

```
copy_test_runner.py      — 测试流水线主程序
  ├─ 读 send_rules.json 拿通道池
  ├─ 调 bowjwj API 创建模板
  ├─ 调 test-send (8 通道并发)
  ├─ 轮询 replay-dashboard 拿结果
  └─ 写 effective_copies.json / tested_copies.json

copy_test_daily_report.py — 每日测试报告生成
```

## 禁区

- ❌ 不走 test-send 单通道模式 (浪费代理线)
- ❌ 测试阶段不 confirm/放量 (只是测试)
- ❌ CTR 不看全量 visits (必须 PH IP)
- ❌ 效果文案库过期不验证不调用 (7 天过期)
- ✅ 自由: 创建模板、test-send、读 replay-dashboard
