---
name: bowjwj-preflight-check
description: Iron rule — before each send session, check plan management for unsent packs and manually trigger send
type: feedback
originSessionId: 32761a31-141a-4fa1-be39-d6d98a7bd3c9
---
## 🔴 铁律: 发信前必须检查计划管理

**每次启动发信前，必须执行：**

```
Step 1: 打开 bowjwj.cc 计划管理/活动管理页面
Step 2: 检查是否有未发出去的包（draft/pending 状态）
Step 3: 逐个点击未发送的包，手动触发发送
Step 4: 确认全部包进入发送队列后，再启动 send_loop.py
```

**Why:** Willy 发现有些包在计划管理里卡住没发出去，需要手动点击才能触发。启动自动发信前必须清空这些积压包。

**How to apply:** 每次 /auto-campaign 或启动 send_loop 前，先检查计划管理中的待发包。
