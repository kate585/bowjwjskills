---
name: bowjwj-source-lock
description: Iron rule — ONLY 凯特ai发送 source packs allowed, all other sources blocked
type: feedback
originSessionId: a10ba864-a171-47e6-902f-018bf6a2532c
---
# 铁律: 只允许凯特ai发送源号码包, 其他包源一律不发 (2026-05-03 Willy)

**Rule**: phone-packs API 必须带 `&source=凯特ai发送` 过滤，客户端双重检查 `src.startswith("凯特ai发送")`。其他来源号码包一概不发。

**Why**: 凯特自己采购的料子质量可控，其他来源质量参差不齐。

**How to apply**:
- send_rules.json: `packRules.sourceMustStartWith = "凯特ai发送"`
- fast_send.py: API 参数加 `&source=凯特ai发送`，客户端 fallback 检查
- 黑名单包自动排: `mustNotContain: ["黑名单"]`
- 禁止清空 sourceMustStartWith 字段
