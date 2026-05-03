---
name: bowjwj-batch-ctr-5pct
description: Iron rule — per-batch CTR target ≥5%, no more rolling average CTR calculation
type: feedback
originSessionId: current
---

## 铁律: 每批次CTR≥5%，不计算均CTR (2026-05-02)

每个发送批次独立检查CTR，目标 **不低于5%**。不再计算和显示滚动平均CTR。

### 规则
- **每批次CTR≥5%** 为正常
- **CTR<5%** → 立即优化文案 + 切换通道
- **CTR<2%** → 优化文案 + 切换通道 + 轮换域名
- **CTR=0%** → 暂停通道 + 全通道轮转

### 显示要求
- RECAP 只显示最近各批次独立CTR，不显示均CTR
- 每个batch CTR 单独打印，标注 ✅/⚠️/🔴

**Why:** 均CTR=3.05% 掩盖了个别批次 0% 的问题。5% 是 Willy 的最低转化预期。

**How to apply:**
- `CTR_THRESHOLD` = 0.05
- `CTR_THRESHOLD_2` = 0.02 (unchanged for immediate action)
- RECAP 移除均CTR行，改为逐批次CTR列表
- `ctr_monitor_loop` 每批次独立判断
