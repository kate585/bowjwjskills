---
name: bowjwj-batch-ctr-check
description: Iron rule — check every individual batch CTR after sending, not just overall average. rawClicks>0 but filtered=0 = bot filter issue → switch to bigger packs (clean≥200)
type: feedback
originSessionId: 6365c4e8-fc05-4de5-8f5d-ed75b46595a1
---
## 铁律: 每批次 CTR 逐包检查 (2026-05-02 Willy 拍板)

**每个发送出去的 batch 必须单独检查 CTR**，不能只看整体平均。整体平均会掩盖个别批次 0% 的问题。

### 检查标准

| batch CTR | rawClicks | 诊断 | 动作 |
|-----------|-----------|------|------|
| **0%** | **0** | 真死流量 — 通道/域名/文案问题 | 切通道 + 换域名 + 优化文案 |
| **0%** | **>0** | Bot filter 太激进 — 链接有效 | 换大包 (clean≥200) 突破过滤阈值 |
| **<2%** | any | 文案/通道不佳 | 换下一个文案方向 + 换通道 |
| **<3%** | any | 低于基线 | 标记观察，连续2次→换方向 |

### 检查频率
- **每轮发送后 90 秒**检查该轮所有 batch 的独立 CTR
- 批量拉 `replay-dashboard/batches` 按创建时间倒序
- 逐个检查最近 25 个 batch

### Why
2026-05-02 发现整体均CTR=3.05% 看似正常，但最近 25 个 batch 中 19 个 CTR=0%。
- 有 rawClicks (10-23) 但 filtered=0 → replay-dashboard 小批次过滤太狠
- 只有大批次 (rawClicks>100) 能通过过滤拿到 2.4-3.0% CTR
- 每包 50 clean → 12包=600条 → rawClicks 只有 10-20 → 全被过滤
- **解决: 必须用 clean≥200 的大包**

### How to apply
```
每个 RECAP 输出后:
1. curl replay-dashboard/batches?pageSize=30
2. 逐行打印 batch CTR + rawClicks + filtered
3. CTR=0%且rawClicks=0 → 标记为真死 🔴
4. CTR=0%且rawClicks>0 → 标记为过滤问题 ⚠️
5. CTR>0 → 标记为正常 ✅
```
