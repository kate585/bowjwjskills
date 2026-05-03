---
name: bowjwj-ctr-3pct-optimize
description: Iron rule: CTR < 3% → immediately optimize copy (换文案/改Taglish/换句式), don't wait
type: feedback
originSessionId: 90be422a-8814-4457-816b-eab01a15d95f
---
## 铁律: CTR降到3%以下立即优化文案 (2026-05-03)

**CTR < 3% → 立即触发文案优化，不等下一轮，不犹豫。**

### 三级响应
| CTR | 动作 |
|-----|------|
| **≥5%** | 达标，正常发送 |
| **3%-5%** | 关注，准备备用文案 |
| **<3%** | 立即优化：换文案/改Taglish/换句式/换方向 |
| **=0%** | 立即停发 + 排查通道/域名/垃圾词 |

### 优化优先级
1. 换文案（从 best_daily_copies_top30.json 取高CTR文案）
2. 改Taglish（更口语化、加菲律宾本地用语）
3. 换句式（对话式开头、金额悬念、限时紧迫感）
4. 换方向（到账通知 → 奖励领取 → 独家VIP）

**Why:** 3%是警戒线，继续发=浪费钱。5%是达标线。

**How to apply:**
- 每轮发完后 T+60s 检查 CTR
- CTR < 3%: 立即停用当前文案，切换到 best_daily_copies 中下一个
- 连续2轮 < 3%: 弃用该文案方向，换全新角度
