---
name: bowjwj-zerocTR-optimize
description: Iron rules for CTR-based copy optimization — CTR=0% immediate stop+rewrite, CTR<3% immediate optimize, CTR<3% for 2 consecutive=abandon direction
type: feedback
originSessionId: 6205bd1d-7b68-4f61-aa39-c50936691099
---

## 铁律: CTR 三级响应 (2026-05-01 Willy 拍板)

| CTR | 动作 | 时限 |
|-----|------|------|
| **CTR = 0%** | ① 立即停发该模板所有包 ② 自动切换通道(从轮换池移除当前通道, 切换到下一个同运营商通道) ③ 自动优化文案(重写换角度, 非微调) ④ 标记旧模板 CTR_ZERO_DEPRECATED | 立即 |
| **CTR < 1%** | 立即触发文案优化: 更口语 Taglish, 对话式开头("i-check mo na", "uy napansin ko lang"), 换句式结构，同批次内替换 | 同批次内 |
| **CTR < 2%** | **立即自动优化**: 触发文案重写(换开头句式/Taglish密度/悬念角度), 不等第二轮, 同批次内替换, 标记旧模板为 UNDERPERFORMING | **立即** |
| **CTR < 3%** | 预警线: 记录到 suspect 队列, 观察是否连续2轮 <3%, 如果是则放弃方向 | 2轮观察期 |
| **CTR < 3% × 2轮** | 放弃该文案方向, 不再复用该角度于同运营商 | 永久 |

## 🔴 铁律: CTR<2% ×2 → 自动换短域名 (2026-05-01 晚上新增)

**CTR<2% 连续2次文案优化无效 → 自动轮换短链域名:**

```
Step 1: CTR<2% 第1次 → 优化文案 (同批次内)
Step 2: CTR<2% 第2次 → 优化文案 ×2 (换角度)
Step 3: 仍然 CTR<2% → rotate_domains(): DOMAIN_IDS 轮转 (pop首→append尾)
Step 4: 同时刷新文案 + 新域名继续发
Step 5: CTR≥3% → 重置 ctr2_optimize_count=0
```

**Why:** 2026-05-01 晚上实测，换域名后 CTR=0% 多个 batch 仍然零点击。但 rawClicks=13-20 存在——说明点击在发生，只是被 replay-dashboard 的 bot 检测过滤了。域名轮换作为兜底手段，确保不会卡在同一个被运营商屏蔽的域名上。

**实现位置:** send_loop.py `ctr2_optimize_count` (line 47), `rotate_domains()` (line 165), CTR monitor handler (line ~775-795)

## ⚠️ rawClicks ≠ 真实点击 (2026-05-01 发现)

**replay-dashboard 会激进过滤点击:**
- batch 级别常见 rawClicks=13-20 但 filtered clicks=0
- CTR=0% 不一定是域名/通道/文案问题——可能只是 bot 过滤太狠
- **不能因为 CTR=0% 就频繁换域名和通道**——每次切换有成本
- 判断标准: 看 rawClicks 趋势。如果 rawClicks 持续增长 → 真人在点，只是被过滤

**How to apply:** CTR=0% 时先检查 rawClicks 字段，不要只看 filtered clicks。rawClicks>0 说明短链接有效，问题在过滤端。

## 🔴 铁律: CTR=0% 自动切换通道 (2026-05-01 新增)

**CTR=0% 时，不等待不犹豫，自动执行三步:**

```
Step 1: 立即从轮换池移除当前通道 (add to CHANNEL_BLOCKED)
Step 2: 自动切换到下一个同运营商通道 (Globe池8个 / Smart池7个)
Step 3: 自动优化文案 (换角度重写, 更口语Taglish/新句式)
Step 4: 用新通道+新文案立即继续发, 不等人
```

**触发条件:** 同一通道×同一模板 CTR=0% (发送后30分钟检查)
**恢复条件:** 24小时后可尝试复用被屏蔽通道
**Why:** 通道风控不会自行恢复, 拖延=浪费钱. 之前GG全网通CTR=0%后仍继续发, 白白浪费多轮.

**Why:** Round 1 (2026-05-01) proved S1=1.1% CTR vs Globe G1=5.7% on same direction. GG全网通 blocked for CTR=0% suspected carrier spam filtering. Every pack sent with CTR<3% is wasted money (~42 PHP/pack minimum). Willy set thresholds: 2% auto-optimize trigger, 3% minimum, 4%+ target.

**How to apply:**
- After every send batch, check replay-dashboard CTR within 5 minutes
- CTR=0%: Stop all packs for that template immediately. Check: 垃圾词, Taglish mix, shortlink domain health, channel status. Rewrite copy with different angle (not just tweak). Mark old template CTR_ZERO_DEPRECATED.
- CTR<1%: Auto-generate optimized variant (more casual Taglish, conversational opener). Deploy within same batch cycle. Do NOT wait for a second round.
- CTR<2%: **立即自动优化** (2026-05-01 落地) — 不等第二轮, 直接触发 optimize_copy_for_carrier(), 同批次内替换. Mark old as UNDERPERFORMING. **连续2次优化后CTR仍<2% → 自动旋转短链域名 (rotate_domains)**.
- CTR<3% for 2 consecutive rounds on same direction: Abandon that copy angle. Don't reuse for same carrier.
- Monitor for 2 consecutive CTR=0 across different copies → escalate to channel health check + shortlink domain blacklist check.
- All CTR measurements use replay-dashboard (PH IP filtered), NOT shortlink visits raw data.
- Target: 3% minimum, 4%+ ideal.
