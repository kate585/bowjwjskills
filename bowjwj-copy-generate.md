---
name: bowjwj-copy-generate
description: bowjwj 运营商话术生成。Willy 说"生成话术"、"AI 写文案"、"新模板"、"改写模板"、"模板创作"、"生成 Globe 话术"、"生成 Smart 话术"、"下一批话术"时加载。Globe/Dito 和 Smart/TNT 两套独立话术池，各自进化。
---

# bowjwj-copy-generate (运营商话术生成)

## 核心原则

**Globe/Dito 和 Smart/TNT 走各自独立的话术方向**，两池不交叉：
- 每池有独立的模板轮换队列、CTR 追踪、exploration→exploitation 阶段
- 运营商用户群行为不同，话术不通用

## 何时触发

**创作**:
- "生成话术" / "AI 写文案" / "新模板"
- "生成 5 个 Globe 话术" / "Smart 要新模板"
- "改写模板 #T" / "AI 改写这个文案"

**轮换**:
- "下一批话术" / "该换模板了" / "换什么话术"
- "Globe 池该换了吗" / "Smart 接下来用什么"

**巡检**:
- "话术池健康吗" / "模板够用吗"

## Globe/Dito 话术池

### 当前 6 方向 (G1-G6)

| 编号 | 方向 | 模板 ID | 文案模板 |
|------|------|---------|----------|
| G1 | 到账+限时 | `16586cb8-...` | `{$phone[10]} may P5,888 na naka-load sa account mo, valid hanggang Apr 30 pwede mo na kunin ${shortUrl}` |
| G2 | 到账+明天到期 | `06758c60-...` | `{$phone[10]} may P6,188 na balance para sa account mo, available pa hanggang bukas, check mo na ${shortUrl}` |
| G3 | 金额悬念 | `b74841ce-...` | `{$phone[10]} meron kang P2,988 na na-add sa wallet, pwede mo na i-check pag may time ka ${shortUrl}` |
| G4 | 更新+金额 | `ba78dbaa-...` | `{$phone[10]} may bago kang update sa account, may naka-ready na P4,588 para sa yo ${shortUrl}` |
| G5 | 朋友语气+到期 | `791e5c6e-...` | `{$phone[10]} uy check mo nga account mo, may P3,888 na naka-pending, baka ma-expire pa ${shortUrl}` |
| G6 | 小额轻松 | `caa55c84-...` | `{$phone[10]} may P1,888 na na-credit sa account mo, sayo na yan pag na-check mo ${shortUrl}` |

### 轮换策略

```
Phase 1 (exploration): 6 方向各测 5000 条 → 找 CTR 最高方向
Phase 2 (exploitation): 锁定最高方向, 每 10000 条换同方向不同话术
换模板触发: total_sent >= rotateEverySends (默认 10000)
```

## Smart/TNT 话术池

### 当前 6 方向 (S1-S6)

| 编号 | 方向 | 模板 ID | 文案模板 |
|------|------|---------|----------|
| S1 | 到账+限时 | `810d7bd4-...` | `{$phone[4]} may P5,888 na naka-load sa account mo, pwede mo na kunin hanggang Apr 30 ${shortUrl}` |
| S2 | 更新+金额 | `bccd5d33-...` | `{$phone[4]} may bago kang P3,288 na balance, check mo na lang pag may time ka ${shortUrl}` |
| S3 | 金额悬念 | `14e1b33a-...` | `{$phone[4]} ready na yung P5,888 mo, pwede mo na i-check pag may time ka ${shortUrl}` |
| S4 | 朋友语气 | `c1913d79-...` | `{$phone[4]} uy may P2,588 na na-credit sa account mo, tingnan mo na ${shortUrl}` |
| S5 | 到期压力 | `95d16f9e-...` | `{$phone[4]} meron kang P4,188 na pending, i-check mo na baka ma-expire pa ${shortUrl}` |
| S6 | 对话式 | `3f366f28-...` | `{$phone[4]} may update lang sa account mo, check na lang pag may time ka ${shortUrl}` |

### 轮换策略 (同 Globe)

## 5 条硬规则 (所有话术必过)

1. **开头不放品牌名大写** — "OKBET:" 冒号格式 = 广告模板信号 (-40 分)
2. **不能全英文** — 植入 1-2 个菲律宾病词 (na/mo/lang/pa)，破坏 Google N-gram 匹配链 (-20 分)
3. **不超过 1 个感叹号** — 多感叹号是垃圾短信经典特征 (-15/个超出)
4. **不用祈使句** — "Claim now" → "pwede mo na makuha" (-25 分)
5. **不超过 145 字符** — 超出算 2 条短信费用 (-30 分)

## 红线一票否决 (碰红线 = score -999，永不使用)

**博彩促销词**: ACT NOW / CLAIM NOW / CLICK NOW / DEPOSIT NOW / URGENT / FREE SPIN / LIMITED TIME / LAST CHANCE / HURRY UP / DON'T MISS

**赌博黑名单英文**: BET / BONUS / DEPOSIT / CASINO / FREE / CLAIM / REWARD / PROMO / SPIN / JACKPOT / RAFFLE / PRIZE

**品牌名**: OKBET / PBAHAY / NN33 (前 30 字符内 + 促销词组合)

**火星文**: R4FFLE / b0nus / Sp1ns / D3POSIT / FR33 / Cl4im / J4ckp0t

## Taglish 病词植入库

| 病词 | 含义 | 用法 | 优先级 |
|------|------|------|--------|
| na | 了/已经 | available na, ready na | ★★★ |
| mo | 你/你的 | check mo, number mo | ★★★ |
| lang | 只是/而已 | quick lang, simple lang | ★★★ |
| pa | 还/再 | active pa, open pa | ★★★ |
| ba | 吗 | seen mo ba? | ★★ |
| ka | 你(主格) | sige ka | ★★ |
| nga | 确实/嘛 | try mo nga | ★★ |
| baka | 说不定 | baka you missed it | ★★ |
| agad | 马上 | check mo agad | ★ |
| talaga | 真的 | it's true talaga | ★ |
| uy | 嘿 | uy check this | ★ |
| sige | 行/来吧 | sige try mo | ★ |

**规则**: 每条话术植入 2-3 个病词，优先 na/mo/lang/pa。

## AI 生成流程

```
触发: 当前池最高分模板 < 60 分 OR Willy 说"生成新话术"

POST /api/campaign-templates/ai-generate
  body: {
    backendInstanceId: "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6",
    aiInstanceId: "cmn0neb160001lnd0xdlc4ty1",  // VAI
    tone: "conversational Taglish, Filipino words na/mo/lang/pa mixed into English, 
           no gambling keywords, no brand names at start, suspense/curiosity tone",
    count: 5
  }

返回 5 候选 → spam_score 打分 → 取最高分 → 自动创建模板
```

## 评分权重 (spam_score)

| 信号 | 分 | 说明 |
|------|-----|------|
| Taglish 短语 (may update / check na lang / pag may time) | +40/条 | 最强防垃圾 |
| Tagalog 词密度 >= 3 | +45 | 本地化 |
| 悬念型 (might be / most useful / 5 seconds) | +25/条 | 英文次优 |
| 问号 | +5/个 | 对话式 |
| Emoji 1-2 个 | +3 | 朋友聊天感 |
| 博彩关键词 (bet/bonus/deposit/casino/free/claim) | **-50/条** | 零容忍 |
| 垃圾词 (URGENT/ACT NOW/HURRY/LAST CHANCE) | -30/条 | 直接进垃圾箱 |
| 开头品牌名+冒号 | -40 | 硬规则 1 |
| 纯英文无菲律宾病词 | -20 | 硬规则 2 |
| 感叹号 >1 | -15/超出 | 硬规则 3 |
| 祈使句 | -25/条 | 硬规则 4 |
| 超 145 字符 | -30 | 硬规则 5 |
| 全大写比例 >30% | -15 | 广告特征 |

## 最高点击文案模式

**到账金额 + 限时领取** = 最高 CTR (经 #68 等 batch 验证)

```
模板: "{$phone[10]} may P5,888 na naka-load sa account mo, 
       valid hanggang Apr 30 pwede mo na kunin ${shortUrl}"
CTR:  11.81% (28 clicks / 237 sent on Globe via GG家全网通)
```

## 变量

- `{$phone[10]}` — 号码后 10 位 (Globe 用)
- `{$phone[4]}` — 号码后 4 位 (Smart 用，更短的变量降低垃圾信号)
- `${shortUrl}` — 短链

## 创建模板 API

```
POST /api/campaign-templates
body: {
  name: "[AI] Globe-<方向>-<日期>",
  activityName: "NN33 New Jackpot",
  campaignType: "activity",
  smsText: "<话术正文>",
  ticketRewardsJson: '[{"ticketType":"FREE_SPIN","ticketId":"2659055","ticketQuantity":1}]',
  backendInstanceId: "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6",
  defaultSendHour: 20
}
```

## 必选票券

- 奖励来源: Urgent Deposit Boost
- 票券: 幸运红包 SMS NN33VIP / ID: 2659055
- **必须选择票券，否则无法发出**

## 数据源

- `send_rules.json` — 两池模板库、轮换状态
- `stats.db.combo_coverage` — 模板级 CTR 历史
- `高点击文案库.txt` — 已验证的高 CTR 文案
- `/api/campaign-templates` — 线上模板 CRUD
- `/api/campaign-templates/ai-generate` — AI 生成

## 禁区

- ❌ 不在对话中穿插博彩品牌名 (OKBET/PBAHAY)
- ❌ 不生成纯英文话术 (必须含菲律宾病词)
- ❌ 不生成含感叹号 >1 的话术
- ❌ 不生成 145 字符以上的话术
- ❌ 不生成含祈使句的话术
- ✅ 自由: GET 模板列表、AI 生成、创建模板 (不触发发送)
