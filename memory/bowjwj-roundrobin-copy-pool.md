---
name: bowjwj-roundrobin-copy-pool
description: Iron rule — use Willy's 14 hand-picked Taglish copy pool for round-robin sending, each with ${shortUrl} variable at end
type: feedback
originSessionId: 05bef769-7f62-4a5e-ac3a-4427eeea3462
---
## 铁律：14条手选文案轮训发送

Willy 精选 14 条 Taglish 文案，每条必须带 `${shortUrl}` 短域名变量。Smart 用 `{$phone[4]}`，Globe 用 `{$phone[10]}`。

**轮训规则：**
- 14 条文案按顺序轮训，每轮每条用一次
- 每轮结束后从第 1 条重新开始
- CTR 监控照常运行（CTR<2% 优化，CTR=0% 切换通道等）

**Why:** AI 生成的文案质量不稳定，手选的 14 条更口语化、Taglish 密度高、CTR 已验证更好。

**How to apply:** 所有新 campaign 必须从这 14 条中轮选。新 AI 生成的模板作为补充池（CTR>5% 才可升级到手选池）。
