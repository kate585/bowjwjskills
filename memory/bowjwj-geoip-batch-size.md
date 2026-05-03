---
name: bowjwj-geoip-batch-size
description: Iron rule — every batch must send 100+ messages per campaign for stable Geo-IP targeting
type: feedback
originSessionId: current
---

## 铁律: 每批至少100+条确保Geo-IP稳定 (2026-05-02)

每轮发送必须达到 **100+条消息**，确保 replay-dashboard 有足够的样本量进行准确的 Geo-IP 过滤。

### 规则
- 每轮 ≥ 100条消息 (目前: 30包 × 50clean = 1500条 ✅)
- 小批次 (<100条) → rawClicks 不足 → bot filter 全过滤 → CTR=0%
- 大批次 (100+) → rawClicks 充足 → 部分通过过滤 → 真实CTR呈现

### 当前配置
- 30 packs/round × 50 clean = **1500条/轮** — 远超100条底线
- 2秒间隔 (密集发送确保同一时间段内累积足够的 rawClicks)

**Why:** 之前12包×50clean=600条，rawClicks只有10-20，全被bot filter过滤掉。加大批次到1500条后 rawClicks 充足，Geo-IP过滤能正确区分菲律宾真实用户 vs US爬虫。

**How to apply:**
- PACKS_PER_CH ≥ 20 (确保 ≥ 1000条/轮)
- SEND_INTERVAL ≤ 3s (密集发送)
- 如 clean≥100 的大包可用，优先使用
