---
name: bowjwj-partner-send
description: bowjwj 合作商单独给料子发信协调器。Willy 说"合作商发信"、"XX合作商给的料子"、"用合作商通道发"、"合作商文案加白"时加载。四步闭环：料子文件 → 加白文案 → 分包指定通道 → 效果反馈。文案走 Taglish 5条硬规则审核，发送走 3秒(自有)/7秒(合作商) 双节奏。
---

# bowjwj-partner-send (合作商给料子发信)

## 何时触发

- Willy 说 "合作商给的料子" / "XX 合作商发信"
- Willy 说 "用合作商通道发" / "对方给料子"
- Willy 说 "合作商文案加白" / "指定文案"
- 指向合作商料子文件 + 指定文案文件时

同时加载 `bowjwj-aicrm` skill 拿 API 地图。

---

## 业务背景

某些合作商（如 NN33 平台方）会单独提供号码包（料子），条件是：
1. **必须使用合作商指定的通道**发送（不能用我们自己的 yo家/GG家 通道）
2. **文案需要经过合作商加白**（合作商提前审核过的文案才能发）
3. 发完后**需要给合作商效果反馈**

这是一个「借通道 + 借料子」模式，和我们自己的「自有料子 + 自有通道」SOP 不同。

---

## 四步闭环

```
合作商给料子文件 ──→ 合作商加白文案文件 ──→ 分包指定合作商通道 ──→ 发送后效果反馈
    (step 1)            (step 2)              (step 3)                (step 4)
```

---

## Step 1: 合作商料子文件 → 识别 & 分包

### 1A. 读取料子文件

合作商给的料子通常是 `.txt` 或 `.csv`，包含手机号列表。确认：
- 文件名记录为合作商标识（如 "NN33平台给的料子 0427"）
- 号码数量
- 运营商分布（如有前缀信息，按 Globe/Smart/Dito/TNT 分组）

### 1B. 上传到 bowjwj

```
POST /api/phone-packs/one-click-import
→ 在 bowjwj 后台生成号码包
→ 记录 phonePackId 列表
```

### 1C. 号码包命名规则

```
<合作商名称> – <日期> – <运营商> <包号>/<总包数>
示例: "NN33合作商料子 – 0427 – Globe 1/5"
```

### 1D. 分包策略

按运营商拆包（和自有料子规则一致）：
- Globe/Dito 号段 → Globe 组
- Smart/TNT 号段 → Smart 组
- 每组单独分包，后续匹配对应运营商的合作商通道

---

## Step 2: 合作商加白文案 → 直接用，不审核

### 2A. 核心原则

合作商的文案是**对方已经加白过的**，我们不做审核、不修改、不筛选。直接拿来发。

```
合作商给什么文案 → 就用什么文案
不要改、不要审、不要筛
改了加白失效，责任在我们
```

### 2B. 我们做什么

1. 读取合作商指定的文案文件
2. 原样录入 bowjwj 模板
3. 直接用于发送

### 2C. Taglish 规则在此处的角色

Taglish 5 条硬规则是我们**自有模板**的质量标准，不用于审核合作商文案。但可作为背景参考：

| # | 规则 | 对合作商文案的意义 |
|---|------|-------------------|
| 1 | 开头不放品牌名大写 | 对方文案如有此问题，到达率可能偏低，**但不改** |
| 2 | Taglish 混搭 | 纯英文点击率通常低于 Taglish，**预期效果可能不如自有模板** |
| 3 | ≤1 个感叹号 | 多感叹号可能触发垃圾箱 |
| 4 | 不用祈使句 | 祈使句可能触发垃圾箱 |
| 5 | ≤145 字符 | 超长算 2 条费用，影响成本 |

> **结论**: 合作商文案一般是纯英文，预期 CTR 会低于我们的 Taglish 模板。这在效果反馈报告里要注明 — 不是通道的问题，是文案风格的问题。

### 2D. 如果要建议合作商优化文案

发过 2-3 轮后有实际 CTR 数据后，可以拿数据跟合作商沟通：
- "这批纯英文文案 CTR X%，我们自己的 Taglish 文案同期 CTR Y%"
- 建议合作商尝试 Taglish 风格并重新加白
- 但绝不替合作商改文案

---

## Step 3: 分包后指定专用通道

### 3A. 通道匹配规则

合作商料子 **必须且只能** 走合作商指定的通道，不能用我们自己的 yo家/GG家 通道。

```
系统中合作商通道的识别特征:
  adapter.name 含 "包料" → 合作商通道（收对方给的号码）
  adapter.name 含 "对方给料" → 合作商通道
  adapter.name 含 "大官人Globe通道" → 合作商通道

这些通道只能发合作商给的号码包，发自有号码包会失败。
```

### 3B. 获取合作商通道

```
已知合作商通道:
  菲律宾短信通道-白羊SMPPTEST（ph地区）0.0052U 加白文案通道
  单价: 0.0052 USD/条 (≈ 0.30 PHP, 比自有通道 0.21 PHP 贵 ~43%)
  地区: PH
  备注: 加白文案通道 — 只收合作商加白过的文案
```

```bash
# 在 bowjwj 系统中反查该通道的 UUID:
GET /api/adapters/instances?type=sms
→ 按 name 模糊匹配 "白羊" 或 "SMPPTEST"
→ 取 id, 确认 enabled=true, backendInstanceIds 含 NN33 BID
```

### 3C. 运营商匹配（合作商通道也要做）

即使走合作商通道，运营商匹配仍然要做：
- Globe 号码包 → 合作商的 Globe 通道
- Smart 号码包 → 合作商的 Smart 通道

如果合作商只提供一个通道（如只支持 Globe），Smart 号段需和合作商确认是否有 Smart 通道，否则 Smart 号段暂不发。

### 3D. 通道分配确认

```
合作商通道分配
━━━━━━━━━━━━━━━━━━━━━━
合作商: NN33平台
通道: 菲律宾短信通道-白羊SMPPTEST（ph地区）0.0052U
单价: 0.0052 USD/条 (自有通道 0.21 PHP ≈ 0.0036 USD)
溢价: ~43%

Globe 号码包 × N包 → 白羊SMPPTEST
Smart 号码包 × M包 → (待确认是否同通道或另配)
```

---

## Step 4: 完成发送后给效果反馈

### 4A. 发送流程

使用 1×1×N 配置（1模板 × 1通道 × N包），走 test-send 先测后放量：

```
POST /api/campaign-templates/{tid}/send-direct/test-send
body:
  templateIds: [合作商加白通过的那条模板 id]
  smsInstanceIds: [合作商专用通道 id]
  phonePackIds: [分包后的号码包 id 列表]
  shortlinkMappingMode: "recipient"
  shortlinkMode: "domain"
  customShortlinkDomainConfigIds: [30 个域名 id]
  titlePrefix: "YYYYMMDD-HHMM-合作商名称"
  plannedAt: "now + 30s"
```

### 4B. 轮询 & 放量

和标准流程一致：
- 轮询 5m30s（阶段 A 密集 + 阶段 B 缓速）
- clickCount >= 2 → 放量（合作商料子质量通常较好，阈值可降至 2）
- 放量用 `/send-direct` + verificationSessionIds

### 4C. 效果反馈报告

发完后 24 小时内，生成合作商反馈报告：

```bash
# 查业务口径数据
GET /api/replay-dashboard/batches/{campaignBatchId}
GET /api/operations-report?backendInstanceId={BID}&createdByUserId={me}&groupBy=campaign
```

```
合作商效果反馈报告
━━━━━━━━━━━━━━━━━━━━━━
合作商: NN33平台
发送时间: 2026-04-27 14:30 BJT
通道: 大官人Globe通道

发送量: 1,500 条
送达量: 1,350 条 (90%)
点击数: 45 次
点击率: 3.33%
注册数: 5 人
FTD数: 1 人
FTD金额: 500 PHP
ROI: 2.1x

短链域名: bonus-now.vip/xxxxx
代理线: nn33idXXX
```

---

## 3秒 vs 7秒 双节奏

合作商发信用 **7秒间隔**，自有料子用 **3秒间隔**。原因：

| 场景 | 间隔 | 原因 |
|------|------|------|
| 自有料子 + 自有通道 | **3秒/包** | 通道是自己的，可全速跑；高峰实测 6.35% CTR |
| 合作商料子 + 合作商通道 | **7秒/包** | 通道是对方的，需保守：避免触发对方限频、给对方 SMPP 压力、保持合作关系 |

### 发送节奏控制

```python
# 合作商发信: cycleSeconds = 7
# 自有发信:   cycleSeconds = 3

def get_cycle_seconds(is_partner_channel: bool, hour: int) -> int:
    if is_partner_channel:
        return 7   # 合作商通道保守节奏
    # 自有通道按 send_rules.json 时段走
    if hour in [7,8, 12, 18,19]:
        return 3   # 高峰
    return 3       # 正常时段也是 3（实测最优）
```

### 预算影响

```
合作商 7秒/包: 3600/7 ≈ 514 包/小时 ≈ 38,550 条/小时
自有   3秒/包: 3600/3 ≈ 1,200 包/小时 ≈ 90,000 条/小时
```

---

## 与合作商相关的本地状态

```
~/.hermes/state/bowjwj/partners/
├── <合作商名称>/
│   ├── source_packs.json       # 合作商给的原始料子信息
│   ├── whitelisted_copy.txt    # 合作商加白过的文案
│   ├── copy_review.json        # Taglish 审核结果
│   ├── rounds/                 # 发送轮次记录
│   └── feedback_YYYYMMDD.json  # 效果反馈报告
```

---

## 禁区

- ❌ 合作商料子**绝不**走自有通道（yo家/GG家）— 会发不出去或触发合作条款
- ❌ 合作商加白文案**绝不修改内容** — 改了加白失效，只能标记「可用/不可用」
- ❌ 不给合作商的反馈里**不暴露**自有通道 CTR/ROI 等商业敏感数据 — 只给合作商料子自身的效果
- ❌ 合作商通道不发自有料子 — 通道侧可能不收
- ✅ 可按自有 SOP 做 test-send → 轮询 → 放量
- ✅ 可用自有短链域名（合作商不管短链）

---

## 首次实跑流程（Willy 盯着）

```
1. Willy 提供合作商料子文件 + 指定文案文件
2. Hermes 读取两个文件，打印摘要（料子数量/运营商分布 + 文案条数）
3. Hermes 查合作商通道（adapter name 含 "包料"/"对方给料"）
4. Hermes 分包 + 运营商匹配
5. Hermes 将合作商文案原样录入模板
6. Willy 扫一眼 → 回 "真跑"
7. Hermes POST test-send（1模板 × 1通道 × N包，cycleSeconds=7）
8. 轮询 5m30s → clickCount>=2 放量
9. T+24h 生成效果反馈报告（含文案风格备注：纯英文 vs Taglish CTR 对比）
```

---

## 更新历史

- 2026-04-27 v1: 首次创建。四步闭环 + Taglish 审核 + 3秒/7秒双节奏。
