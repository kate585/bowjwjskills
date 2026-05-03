---
name: feedback_monitor_response
description: Background monitor notifications should not be acknowledged individually — only alert on actual anomalies
type: feedback
originSessionId: 4c7d1a98-7a0b-4356-aafa-fb58cc50bb7d
---
**Rule:** When a background monitoring task (Monitor tool or CronCreate) emits normal status notifications, do NOT reply with individual acknowledgements like "正常".

**Why:** The user explicitly asked to be notified only when there's an anomaly (e.g., 3 consecutive zero-click packs). Replying to every normal check floods the conversation with noise.

**How to apply:** Stay silent on normal check-in events. Only respond when the monitor detects an actual alert condition OR the user sends a direct message. The user knows the monitor is running.
